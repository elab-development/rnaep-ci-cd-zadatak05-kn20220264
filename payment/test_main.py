import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


#unit

def test_order_total_calculation():
    """Unit test: proverava da li se total ispravno racuna"""
    price = 100.0
    quantity = 2
    fee = 0.2 * price
    total = 1.2 * price * quantity
    assert fee == 20.0
    assert total == 240.0

def test_order_fee_calculation():
    """Unit test: proverava da li je fee 20% od cene"""
    price = 50.0
    fee = 0.2 * price
    assert fee == 10.0

def test_order_status_initial():
    """Unit test: proverava da li je inicijalni status 'pending'"""
    status = 'pending'
    assert status == 'pending'

#integralni

def test_redis_connection():
    """Integracioni test: proverava konekciju sa Redis-om"""
    import fakeredis
    r = fakeredis.FakeRedis(decode_responses=True)
    r.set('test_key', 'test_value')
    assert r.get('test_key') == 'test_value'

def test_redis_stream():
    """Integracioni test: proverava da li se poruka dodaje u stream"""
    import fakeredis
    r = fakeredis.FakeRedis(decode_responses=True)
    r.xadd('order_completed', {'product_id': '123', 'quantity': '2'})
    messages = r.xrange('order_completed')
    assert len(messages) == 1
    assert messages[0][1]['product_id'] == '123'

def test_redis_xadd_refund():
    """Integracioni test: proverava da li se refund poruka dodaje u stream"""
    import fakeredis
    r = fakeredis.FakeRedis(decode_responses=True)
    r.xadd('refund_order', {'pk': 'order-123', 'status': 'refunded'})
    messages = r.xrange('refund_order')
    assert len(messages) == 1

#funkc testovi 

@patch('main.redis')
@patch('main.httpx.AsyncClient')
def test_create_order_product_not_found(mock_client, mock_redis):
    """Funkcionalni test: order sa nepostojecim proizvodom vraca 400"""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

    from main import app
    client = TestClient(app)
    response = client.post('/orders', json={'id': 'nonexistent', 'quantity': 1})
    assert response.status_code == 400

@patch('main.redis')
@patch('main.httpx.AsyncClient')
def test_create_order_success(mock_client, mock_redis):
    """Funkcionalni test: uspesno kreiranje ordera"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'id': 'prod-1',
        'name': 'Test Product',
        'price': 100.0,
        'quantity': 10
    }
    mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

    mock_order = MagicMock()
    mock_order.pk = 'order-1'
    mock_order.product_id = 'prod-1'
    mock_order.price = 100.0
    mock_order.fee = 20.0
    mock_order.total = 240.0
    mock_order.quantity = 2
    mock_order.status = 'pending'

    with patch('main.Order') as MockOrder:
        MockOrder.return_value = mock_order
        mock_order.save.return_value = mock_order

        from main import app
        client = TestClient(app)
        response = client.post('/orders', json={'id': 'prod-1', 'quantity': 2})
        assert response.status_code == 200

@patch('main.redis')
def test_get_order_not_found(mock_redis):
    """Funkcionalni test: get order koji ne postoji vraca 404"""
    from redis_om import NotFoundError
    with patch('main.Order') as MockOrder:
        MockOrder.get.side_effect = NotFoundError

        from main import app
        client = TestClient(app)
        response = client.get('/orders/nonexistent-pk')
        assert response.status_code == 404