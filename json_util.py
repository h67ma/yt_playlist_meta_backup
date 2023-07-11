import json


def load_json(json_path: str) -> object:
	try:
		with open(json_path, "r") as f:
			return json.load(f)
	except:
		return None


def save_json(obj: object, json_path: str):
	with open(json_path, "w") as f:
		json.dump(obj, f, indent='\t')
