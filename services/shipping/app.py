import json
import requests
from os import environ
from pydantic import BaseModel
from fastapi import FastAPI, Header, HTTPException

BASE_URL = 'https://www.eleganceoutletbsb.com.br'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
CHECKOUT_API_URL = 'https://checkout-api.ms.tiendanube.com/checkout/v3/new-shipping-options'

app = FastAPI()

class Variant(BaseModel):
	id: str
	name: str
	product_id: str
	quantity: int

class Request(BaseModel):
	zipcode: str
	variants: list[Variant]

def request_wrapper(
	session: requests.Session,
	url: str,
	method: str = 'post',
	data: dict = {},
	headers: dict = {},
	params: dict = {},
	**kwargs
):
	def debug_field(field, name):
		if field:
			lines = "\n".join(f"{key}: {value}" for key, value in field.items())
			print(f'{name}:\n{lines}\n----\n')

	print(f'Performing {method.upper()} on {url}')
	debug_field(data, 'POST fields')
	debug_field(headers, 'Headers')
	debug_field(params, 'GET fields')

	res = getattr(session, method)(url, data = data, headers = headers, params = params, **kwargs)

	print(f'Response ({res.status_code}): {json.dumps(res.text[:300] + ("..." if len(res.text) > 300 else ""))}')

	return res

def add_to_cart(session: requests.Session, variant: Variant) -> requests.Response:
	return request_wrapper(
		session,
		f'{BASE_URL}/comprar/',
		data = {
			'add_to_cart': variant.product_id,
			'variant_id': variant.id,
			'variation[0]': variant.name,
			'quantity': variant.quantity,
			'zipcode': '',
			'add_to_cart_enhanced': '1'
		},
		headers = {
			'X-Requested-With': 'XMLHttpRequest'
		}
	)

def go_to_checkout(session: requests.Session, products: list[dict]) -> str:
	res = request_wrapper(
		session,
		f'{BASE_URL}/comprar/',
		data = {
			**{f'quantity[{product.get("id")}]': product.get("quantity") for product in products},
			'go_to_checkout': 'Iniciar Compra'
		}
	)

	access_token = None

	for key, value in res.cookies.items():
		if key.startswith('access_token_'):
			access_token = value
			break

	return access_token

def get_shipping_data(
	session: requests.Session,
	zipcode: str,
	cart: dict,
	access_token: str,
	keys: list[str] = []
) -> dict:
	res = request_wrapper(
		session,
		CHECKOUT_API_URL,
		method = 'get',
		params = {
			'cartId': cart.get('id'),
			'zipcode': zipcode,
			'country': 'BR',
			'keepCartAddress': 'false',
			'city': '',
			'orderId': cart.get('id')
		},
		headers = {
			'Authorization': f'Bearer {access_token}'
		}
	)
	json_res = res.json()

	if 'errors' in json_res:
		return {'error': True, 'message': 'Falhou em calcular frete', 'data': json_res}

	shipping_data = json_res.get('shipping_options', [])

	if len(keys):
		shipping_data = list({key: option.get(key) for key in keys} for option in shipping_data)

	return {'error': False, 'shipping_options': shipping_data}

@app.post('/shipping')
def shipping(data: Request, token: str = Header(...)) -> dict:
	env_token = environ.get('TOKEN')

	if env_token is None or env_token != token:
		raise HTTPException(403, 'Invalid access token')

	session = requests.Session()
	session.headers = {
		'User-Agent': USER_AGENT,
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
		'Accept-Language': 'pt-BR,pt;q=0.9'
	}
	failed = []

	for variant in data.variants:
		json_res = add_to_cart(session, variant).json()

		if not json_res.get('success'):
			failed.append({
				'response': json_res,
				'variant_id': variant.id,
				'product_id': variant.product_id
			})

	if failed:
		return {
			'error': True,
			'message': 'Falhou ao adicionar produtos ao carrinho',
			'data': failed
		}

	cart = json_res.get('cart', {})
	products = cart.get('products', [])

	print(f'cart id: {cart.get("id")}')

	checkout_token = go_to_checkout(session, products)

	if checkout_token is None:
		return {'error': True, 'message': 'Falhou em calcular o frete'}

	print(f'checkout token: {checkout_token}')

	return get_shipping_data(session, data.zipcode, cart, checkout_token)