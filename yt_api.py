import os
import re
import copy
import requests
from typing import List
from datetime import datetime
import google_auth_oauthlib.flow
import googleapiclient.discovery

from consts import *
from util import get_thumb_list, datetime_to_timestamp

CLIENT_SECRETS_FILE = "secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
MAX_LIST_RESULTS = 50 # more is not allowed by the API

API_KEY_ID = "id"
API_KEY_VID_ID = "videoId"
API_KEY_ITEMS = "items"
API_KEY_CHANNEL_TITLE = "channelTitle"
API_KEY_NEXT_PAGE_TOKEN = "nextPageToken"
API_KEY_CONTENT_DETAILS = "contentDetails"
API_KEY_SNIPPET = "snippet"
API_KEY_STATUS = "status"
API_KEY_PRIVACY_STATUS = "privacyStatus"
API_KEY_NOTE = "note"
API_KEY_DESCRIPTION = "description"
API_KEY_THUMBS = "thumbnails"
API_KEY_PLAYLIST_OWNER_CHANNEL_ID = "channelId"
API_KEY_OWNER_CHANNEL_NAME = "videoOwnerChannelTitle"
API_KEY_OWNER_CHANNEL_ID = "videoOwnerChannelId"
API_KEY_CHANNEL_NAME = "videoOwnerChannelTitle"
API_KEY_TITLE = "title"
API_KEY_WIDTH = "width"
API_KEY_URL = "url"
API_KEY_PUBLISHED_AT = "videoPublishedAt"
API_KEY_ADDED_TO_PLAYLIST = "publishedAt" # I guess "published to playlist"


reg_extract_playlist_id = re.compile(r"list=([a-zA-Z0-9\-_]+)(?:&|$)")


def timestring_to_timestamp(timestring: str) -> int:
	return datetime_to_timestamp(datetime.strptime(timestring, '%Y-%m-%dT%H:%M:%SZ'))


def make_part_string(parts: List[str]) -> str:
	return ','.join(parts)


def dump_playlist(youtube_api, playlist: object, thumbs_dir_path: str, no_thumbs: bool, thumb_list: List[str]):
	playlist_id = playlist[API_KEY_ID]
	playlist_title = playlist[API_KEY_SNIPPET][API_KEY_TITLE]

	print("Fetching %s..." % playlist_title)

	thumb_dlded_cnt = 0
	videos_on_playlist_full = []
	videos_on_playlist_refs = []
	next_page_token = None
	page_number = 1
	while True:
		print("  Fetching videos page %s..." % page_number)
		page_number += 1

		request = youtube_api.playlistItems().list(
			part=make_part_string([API_KEY_SNIPPET, API_KEY_STATUS, API_KEY_CONTENT_DETAILS]),
			maxResults=MAX_LIST_RESULTS,
			playlistId=playlist_id,
			pageToken=next_page_token
		)
		playlist_content_response = request.execute()

		for video in playlist_content_response[API_KEY_ITEMS]:
			vid_data = {}
			vid_data_minimal = {}

			vid_id = video[API_KEY_CONTENT_DETAILS].get(API_KEY_VID_ID)

			if vid_id is None:
				print("Video missing id, skipping")
				continue

			vid_data[JSON_KEY_ID] = vid_id
			vid_data_minimal[JSON_KEY_ID] = vid_id

			if API_KEY_TITLE in video[API_KEY_SNIPPET]:
				vid_data[JSON_KEY_TITLE] = video[API_KEY_SNIPPET][API_KEY_TITLE]

			if API_KEY_OWNER_CHANNEL_NAME in video[API_KEY_SNIPPET]:
				vid_data[JSON_KEY_CHANNEL_NAME] = video[API_KEY_SNIPPET][API_KEY_OWNER_CHANNEL_NAME]

			if API_KEY_OWNER_CHANNEL_ID in video[API_KEY_SNIPPET]:
				vid_data[JSON_KEY_CHANNEL_ID] = video[API_KEY_SNIPPET][API_KEY_OWNER_CHANNEL_ID]

			if API_KEY_ADDED_TO_PLAYLIST in video[API_KEY_SNIPPET]:
				vid_data_minimal[JSON_KEY_ADDED_TIME] = timestring_to_timestamp(video[API_KEY_SNIPPET][API_KEY_ADDED_TO_PLAYLIST])

			if API_KEY_DESCRIPTION in video[API_KEY_SNIPPET]:
				vid_data[JSON_KEY_DESCRIPTION] = video[API_KEY_SNIPPET][API_KEY_DESCRIPTION]

			if API_KEY_PRIVACY_STATUS in video[API_KEY_STATUS]:
				vid_data[JSON_KEY_STATUS] = video[API_KEY_STATUS][API_KEY_PRIVACY_STATUS]

			if API_KEY_PUBLISHED_AT in video[API_KEY_CONTENT_DETAILS]:
				vid_data[JSON_KEY_PUBLISHED] = timestring_to_timestamp(video[API_KEY_CONTENT_DETAILS][API_KEY_PUBLISHED_AT])

			# note: video duration is not included here - we'd need a separate API call for each video.
			# since it's not too important, skip it.

			if API_KEY_THUMBS in video[API_KEY_SNIPPET] and len(video[API_KEY_SNIPPET][API_KEY_THUMBS]) > 0:
				thumbs = video[API_KEY_SNIPPET][API_KEY_THUMBS]

				# if thumbnail is already downloaded, skip redownloading
				if not no_thumbs and vid_id not in thumb_list:
					# find thumb of biggest size
					best_size = sorted(thumbs, key=lambda k: thumbs[k][API_KEY_WIDTH], reverse=True)[0]
					best_thumb_url = thumbs[best_size][API_KEY_URL]
					best_thumb_filename = vid_id + ".jpg"

					# download thumb
					remote_file = requests.get(best_thumb_url)
					with open(os.path.join(thumbs_dir_path, best_thumb_filename), "wb") as f:
						f.write(remote_file.content)

					thumb_list.append(vid_id)
					thumb_dlded_cnt += 1

			videos_on_playlist_full.append(vid_data)
			videos_on_playlist_refs.append(vid_data_minimal)

		if API_KEY_NEXT_PAGE_TOKEN in playlist_content_response:
			next_page_token = playlist_content_response[API_KEY_NEXT_PAGE_TOKEN]
		else:
			break

	full_playlist = {
		JSON_KEY_ID: playlist_id,
		JSON_KEY_CHANNEL_NAME: playlist[API_KEY_SNIPPET][API_KEY_CHANNEL_TITLE],
		JSON_KEY_CHANNEL_ID: playlist[API_KEY_SNIPPET][API_KEY_PLAYLIST_OWNER_CHANNEL_ID],
		JSON_KEY_STATUS: playlist[API_KEY_STATUS][API_KEY_PRIVACY_STATUS],
		JSON_KEY_TITLE: playlist_title,
		JSON_KEY_DESCRIPTION: playlist[API_KEY_SNIPPET][API_KEY_DESCRIPTION]
	}

	refs_playlist = copy.deepcopy(full_playlist)

	full_playlist[JSON_KEY_VIDEOS] = videos_on_playlist_full
	refs_playlist[JSON_KEY_VIDEOS] = videos_on_playlist_refs

	return full_playlist, refs_playlist, thumb_dlded_cnt


def build_yt_api_object():
	flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
	credentials = flow.run_local_server()
	return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)


def dump_account_playlists(youtube_api, thumbs_dir_path: str, no_thumbs: bool, time_now: datetime):
	thumb_list = get_thumb_list(thumbs_dir_path)
	thumb_dlded_cnt = 0

	dump_full = []
	refs_playlists = []

	next_page_token = None
	page_number = 1
	while True:
		print("Fetching playlists page %s..." % page_number)
		page_number += 1

		request = youtube_api.playlists().list(
			part=make_part_string([API_KEY_SNIPPET, API_KEY_STATUS]),
			maxResults=MAX_LIST_RESULTS,
			mine=True,
			pageToken=next_page_token
		)
		playlist_response = request.execute()

		for playlist in playlist_response[API_KEY_ITEMS]:
			full_playlist, refs_playlist, playlist_thumb_dlded_cnt = dump_playlist(youtube_api, playlist, thumbs_dir_path, no_thumbs, thumb_list)

			thumb_dlded_cnt += playlist_thumb_dlded_cnt
			dump_full.append(full_playlist)
			refs_playlists.append(refs_playlist)

		if API_KEY_NEXT_PAGE_TOKEN not in playlist_response:
			break

		next_page_token = playlist_response[API_KEY_NEXT_PAGE_TOKEN]

	dump_refs = {
		JSON_KEY_DUMP_TIME: int(time_now.timestamp()),
		JSON_KEY_PLAYLISTS: refs_playlists
	}

	if not no_thumbs:
		print("Downloaded", thumb_dlded_cnt, "new thumbnails")

	return dump_full, dump_refs


def read_list_of_playlists_file(path: str) -> List[str]:
	"""
	Reads the list file.
	The file should contain links to playlists or playlist IDs separated by newline.
	"""
	playlist_ids = []
	try:
		with open(path, "r") as f:
			for line in f:
				line = line.strip()
				if len(line) == 0:
					continue

				match = reg_extract_playlist_id.findall(line)
				if len(match) == 1:
					playlist_ids.append(match[0])
				else:
					# either a raw id, or garbage
					playlist_ids.append(line)
	except FileNotFoundError as ex:
		print(ex)
		return None

	return playlist_ids


def dump_playlist_meta(youtube_api, playlist_ids: List[str]):
	"""
	Split the list of IDs into groups counting maximum of MAX_LIST_RESULTS, so that
	they can be passed to a single API call. Don't use next page token as we don't expect the result to be paginated.
	Combine all API calls results into one list and return it.
	"""
	playlists_meta = []
	low = 0
	high = MAX_LIST_RESULTS
	page_number = 1
	while len(playlist_ids[low:high]) > 0:
		print("Fetching playlist metadata page %s..." % page_number)
		query_ids = make_part_string(playlist_ids[low:high])
		low += MAX_LIST_RESULTS
		high += MAX_LIST_RESULTS
		page_number += 1

		request = youtube_api.playlists().list(
			part=make_part_string([API_KEY_SNIPPET, API_KEY_STATUS]),
			id=query_ids,
			maxResults=MAX_LIST_RESULTS
		)
		playlists_response = request.execute()

		playlists_meta.extend(playlists_response[API_KEY_ITEMS])

		if API_KEY_NEXT_PAGE_TOKEN in playlists_response:
			print("Warning: next page token unexpected")

	return playlists_meta


def dump_list_of_playlists(youtube_api, thumbs_dir_path: str, no_thumbs: bool, time_now: datetime, list_path: str):
	thumb_list = get_thumb_list(thumbs_dir_path)
	thumb_dlded_cnt = 0

	dump_full = []
	refs_playlists = []

	playlist_ids = read_list_of_playlists_file(list_path)
	if playlist_ids is None:
		return None, None

	playlist_meta = dump_playlist_meta(youtube_api, playlist_ids)
	for playlist in playlist_meta:
		full_playlist, refs_playlist, playlist_thumb_dlded_cnt = dump_playlist(youtube_api, playlist, thumbs_dir_path, no_thumbs, thumb_list)

		thumb_dlded_cnt += playlist_thumb_dlded_cnt
		dump_full.append(full_playlist)
		refs_playlists.append(refs_playlist)

	dump_refs = {
		JSON_KEY_DUMP_TIME: int(time_now.timestamp()),
		JSON_KEY_PLAYLISTS: refs_playlists
	}

	if not no_thumbs:
		print("Downloaded", thumb_dlded_cnt, "new thumbnails")

	return dump_full, dump_refs
