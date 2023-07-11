import os
import re
import pathlib
from typing import List
from datetime import datetime


reg_sanitize = re.compile(r"[^A-Za-z0-9_\-[\]()\.!&+]")


def get_file_title_from_path(path: str) -> str:
	return pathlib.Path(path).stem


def sanitize_filename(title: str) -> str:
	return reg_sanitize.sub("_", title)


def get_thumb_list(thumb_dir: str) -> List[str]:
	"""
	Returns a list of video ids that have a thumbnail downloaded.
	"""
	return [get_file_title_from_path(f) for f in os.listdir(thumb_dir)]


def datetime_to_timestring(date_time: datetime) -> str:
	return date_time.strftime("%Y-%m-%d_%H-%M-%S")


def datetime_to_timestamp(date_time: datetime) -> int:
	return int(date_time.timestamp())
