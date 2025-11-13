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

def add_to_cart(session: requests.Session, variant: Variant) -> requests.Response:
	return session.post(
		f'{BASE_URL}/comprar/',
		data = {
			'add_to_cart': variant.product_id,
			'variant_id': variant.id,
			'variant[0]': variant.name,
			'quantity': variant.quantity,
			'zipcode': '',
			'add_to_cart_enhanced': '1'
		},
		headers = {
			'X-Requested-With': 'XMLHttpRequest'
		}
	)

def go_to_checkout(session: requests.Session, products: list[dict]) -> str:
	res = session.post(
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
) -> list[dict]:
	res = session.get(
		CHECKOUT_API_URL,
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
	shipping_data = res.json().get('shipping_options', [])

	if len(keys):
		shipping_data = list({key: option.get(key) for key in keys} for option in shipping_data)

	return shipping_data

@app.post('/shipping')
def shipping(data: Request, token: str = Header(...)) -> list:
	env_token = environ.get('TOKEN')

	if env_token is None or env_token != token:
		raise HTTPException(403, 'Invalid access token')

	session = requests.Session()
	session.headers = {
		'User-Agent': USER_AGENT,
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
		'Accept-Language': 'pt-BR,pt;q=0.9'
	}

	for variant in data.variants:
		res = add_to_cart(session, variant)
		print(f'site response: ({res.status_code}) \"{res.text}\"')

	cart = res.json().get('cart', {})
	products = cart.get('products', [])

	print(f'cart id: {cart.get("id")}')

	checkout_token = go_to_checkout(session, products)

	print(f'checkout token: {checkout_token}')

	return get_shipping_data(session, data.zipcode, cart, checkout_token)