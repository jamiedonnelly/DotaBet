from urllib.error import HTTPError
import aiohttp 
import json 
import requests
import asyncio 
from collections import OrderedDict
from io import BytesIO

def raise_error(url, code, errors):
	template = errors.get(code, errors.get("default", "Http request failed with a {} error"))
	if code == 404:
		raise Http404Error(template)
	else:
		raise HttpError(template, code)

class HttpGetter:
	def __init__(self):
		self.loop = asyncio.get_event_loop()
		self.session = aiohttp.ClientSession(loop=self.loop)

	async def get(self, url, return_type="json", headers=None):

		async with self.session.get(url, timeout=60) as r:
			if r.status == 200:
				if return_type == "json":
				    return json.loads(await r.text(), object_pairs_hook=OrderedDict)
				elif return_type == "text":
				    return  await r.text()
				elif return_type == "bytes":
				    return BytesIO(await r.read())
				else:
                                    raise ValueError(f"Invalid return type '{return_type}'")
			else:
				raise ValueError(url)


	async def post(self, url, return_type="json", body={}, headers={}):
		async with self.session.post(url, json=body, headers=headers) as r:
			if r.status == 200:
				if return_type == "json":
					return json.loads(await r.text(), object_pairs_hook=OrderedDict)
				elif return_type == "text":
					return await r.text()
				elif return_type == "bytes":
					return BytesIO(await r.read())
				else:
					raise ValueError(f"Invalid return type '{return_type}'")
			else:
				raise ValueError(url)

            

