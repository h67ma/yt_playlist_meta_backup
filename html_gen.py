import os
import re
from datetime import datetime
from typing import Tuple

from consts import *
from util import sanitize_filename, get_thumb_list


STATUS_DEFAULT_COLOR = "#D0D"
STATUS_STR_TO_COLOR = {
	STATUS_UNSPEC: STATUS_DEFAULT_COLOR,
	STATUS_PRIVATE: "#C00",
	STATUS_UNLISTED: "#D70",
	STATUS_PUBLIC: "#0C0",
	STATUS_PUBLIC_OR_UNLISTED: "#6B6",
}

UNKNOWN_NAME = "???"

reg_unmultinewline = re.compile(r"\n+")


def sanitize_display_string(input: str) -> str:
	"""
	note: yt seems to not allow < and > in titles/descriptions/channel names
	but better to remove them just in case
	"""
	return input.replace('<', "&lt;").replace('>', "&gt;")


def add_newlines(input: str) -> str:
	return reg_unmultinewline.sub('\n', input).replace('\n', "<br />\n")


def status_str_to_color(status: str) -> str:
	return STATUS_STR_TO_COLOR.get(status, STATUS_DEFAULT_COLOR)


def timestamp_to_datestring(timestamp: int) -> str:
	return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def get_channel_url_from_id(channel_id: str) -> str:
	return "https://www.youtube.com/channel/" + channel_id


def duration_to_timestring(seconds: int) -> str:
	minutes, seconds = divmod(seconds, 60)
	hours, minutes = divmod(minutes, 60)
	if hours > 0:
		return "%d:%02d:%02d" % (hours, minutes, seconds)
	
	return "%d:%02d" % (minutes, seconds)


def is_snapshot_useful(status: str) -> bool:
	"""
	Returns True if snapshot metadata has useful info (unlisted, public),
	or False if it doesn't have any useful info (private, unspecified, ...)
	"""
	return status in [STATUS_UNLISTED, STATUS_PUBLIC, STATUS_PUBLIC_OR_UNLISTED]


def select_snapshot(snapshots: object, requested_timestamp: int) -> Tuple[object, int]:
	"""
	Selects video metadata snapshot from database based on timestamp. As not all timestamp values are expected to exist
	in the database (timestamp is bumped when metadata is the same), select the oldest one with timestamp greater or
	equal to requested one. If the selected one's status is private or unspecified, select any other snapshot, just so
	we have any data to display.

	Note: unfortunately json keys are strings - convert them to ints for sorting

	@snapshots: dictionary mapping timestamp to video metadata
	@requested_timestamp: requested timestamp

	@returns: tuple(
		video metadata object (can be empty),
		timestamp of the returned metadata or None if no suitable snapshot was found,
	)
	"""
	int_keys = sorted([int(key) for key in snapshots.keys()])

	for snapshot_timestamp in int_keys:
		if snapshot_timestamp >= requested_timestamp:
			# found a snapshot with correct timestamp

			snapshot = snapshots[str(snapshot_timestamp)]

			real_status = snapshots[str(snapshot_timestamp)][JSON_KEY_STATUS]
			if not is_snapshot_useful(real_status):
				# this snapshot does not contain any meaningful data, only status is relevant
				break

			# this snapshot contains meaningful data
			return snapshots[str(snapshot_timestamp)], snapshot_timestamp

	# we've searched through snapshots and couldn't find a proper one,
	# or we found it but it was private/unspecified and didn't contain data.
	# just select any snapshot that contains data
	for snapshot_timestamp, snapshot in snapshots.items():
		if is_snapshot_useful(snapshot[JSON_KEY_STATUS]):
			if real_status is not None:
				snapshot[JSON_KEY_STATUS] = real_status
			return snapshot, int(snapshot_timestamp)

	# we couldn't find any snapshot that contained any meaningful data :(
	# return only status if it is even set

	out = {}

	if real_status is not None:
		out[JSON_KEY_STATUS] = real_status

	return out, None


def generate_html(db: object, dump: object, output_dir: str, thumbs_dir_path: str):
	os.makedirs(output_dir, exist_ok=True)

	print("Writing to", output_dir)

	for required_key in [JSON_KEY_PLAYLISTS, JSON_KEY_DUMP_TIME]:
		if required_key not in dump:
			print("\"%s\" missing from dump, aborting" % required_key)
			return

	thumb_list = get_thumb_list(thumbs_dir_path)

	dump_time = dump[JSON_KEY_DUMP_TIME]
	dump_time_str = timestamp_to_datestring(dump_time)

	for playlist in dump[JSON_KEY_PLAYLISTS]:
		for required_key in [JSON_KEY_TITLE, JSON_KEY_VIDEOS]:
			if required_key not in playlist:
				print("\"%s\" missing from playlist, skipping" % required_key)
				continue

		playlist_title = playlist[JSON_KEY_TITLE]
		output_path = os.path.join(output_dir, sanitize_filename(playlist_title) + ".html")

		print("Processing", playlist_title)

		playlist_title = sanitize_display_string(playlist_title)

		### header ###
		out_html = "<!DOCTYPE html>\n<html>\n<head>\n<title>%s</title>\n</head>\n<body>\n" % playlist_title

		### playlist info ###

		out_info = "<b>Dump time</b>: %s" % dump_time_str

		if JSON_KEY_ID in playlist:
			playlist_url = "https://www.youtube.com/playlist?list=" + playlist[JSON_KEY_ID]
			out_info += "<br />\n<b>Title</b>: <a href=\"%s\">%s</a>" % (playlist_url, playlist_title)
		else:
			out_info += "<br />\n<b>Title</b>: %s" % playlist_title

		if JSON_KEY_CHANNEL_NAME in playlist:
			channel_name = sanitize_display_string(playlist[JSON_KEY_CHANNEL_NAME])
			if JSON_KEY_CHANNEL_ID in playlist:
				channel_url = get_channel_url_from_id(playlist[JSON_KEY_CHANNEL_ID])
				out_info += "<br />\n<b>Channel</b>: <a href=\"%s\">%s</a>" % (channel_url, channel_name)
			else:
				out_info += "<br />\n<b>Channel</b>: %s" % channel_name

		if JSON_KEY_STATUS in playlist:
			color = status_str_to_color(playlist[JSON_KEY_STATUS])
			out_info += "<br />\n<b>Status</b>: <span style=\"color: %s;\">%s</span>" % (color, playlist[JSON_KEY_STATUS])

		if JSON_KEY_DESCRIPTION in playlist:
			out_info += "<br />\n<b>Description</b>: %s" % add_newlines(sanitize_display_string(playlist[JSON_KEY_DESCRIPTION]))

		### videos table ###

		out_table = """
<table border="1" cellpadding="5" cellspacing="0">
<tr>
	<th>Thumbnail</th>
	<th width="600">Metadata</th>
	<th width="600">Description</th>
</tr>
"""

		status_counts = { key: 0 for key in KNOWN_STATUSES }

		for video in playlist[JSON_KEY_VIDEOS]:
			if JSON_KEY_ID not in video:
				print("Video missing id, skipping")
				continue

			vid_id = video[JSON_KEY_ID]

			# find video metadata in database
			if vid_id not in db:
				print("Cannot find in database:", vid_id)
			else:
				# select the correct snapshot
				vid_meta, vid_meta_timestamp = select_snapshot(db[vid_id], dump_time)

			vid_url = "https://www.youtube.com/watch?v=" + vid_id

			out_video = "<tr><td>"

			# thumbnail

			if vid_id in thumb_list:
				out_video += "<a href=\"%s\"><img src=\"../../%s/%s.jpg\" width=\"400\" /></a>" % (vid_url, DIR_THUMBS, vid_id)

			out_video += "</td><td>"

			# metadata

			if JSON_KEY_TITLE in vid_meta:
				vid_title = sanitize_display_string(vid_meta[JSON_KEY_TITLE])
			else:
				vid_title = UNKNOWN_NAME

			out_video += "\n<b>Title</b>: <a href=\"%s\">%s</a>" % (vid_url, vid_title)

			channel_url = None
			if JSON_KEY_CHANNEL_ID in vid_meta:
				channel_url = get_channel_url_from_id(vid_meta[JSON_KEY_CHANNEL_ID])

			# note: in the past yt used to have channel urls like "https://youtube.com/user/ChannelName",
			# but it doesn't seem to work anymore. keep username in JSON_KEY_CHANNEL_USERNAME just in case

			channel_name = None
			if JSON_KEY_CHANNEL_NAME in vid_meta:
				channel_name = sanitize_display_string(vid_meta[JSON_KEY_CHANNEL_NAME])

			if channel_url is not None and channel_name is not None:
				out_video += "<br />\n<b>Channel</b>: <a href=\"%s\">%s</a>" % (channel_url, channel_name)
			elif channel_url is None and channel_name is not None:
				out_video += "<br />\n<b>Channel</b>: %s" % channel_name
			elif channel_url is not None:
				out_video += "<br />\n<b>Channel</b>: <a href=\"%s\">%s</a>" % (channel_url, UNKNOWN_NAME)

			if JSON_KEY_DURATION in vid_meta:
				out_video += "<br />\n<b>Duration</b>: " + duration_to_timestring(vid_meta[JSON_KEY_DURATION])

			if JSON_KEY_STATUS in vid_meta:
				vid_status = vid_meta[JSON_KEY_STATUS]

				if vid_status in KNOWN_STATUSES:
					status_counts[vid_status] += 1
				else:
					status_counts[STATUS_UNSPEC] += 1

				color = status_str_to_color(vid_status)
				out_video += "<br />\n<b>Status</b>: <span style=\"color: %s;\">%s</span>" % (color, vid_status)
			else:
				status_counts[STATUS_UNSPEC] += 1

			out_video += "<br />\n<b>Thumbs</b>: "
			out_video += "<a href=\"https://i.ytimg.com/vi/%s/default.jpg\">[1]</a> " % vid_id
			out_video += "<a href=\"https://i.ytimg.com/vi/%s/mqdefault.jpg\">[2]</a> " % vid_id
			out_video += "<a href=\"https://i.ytimg.com/vi/%s/hqdefault.jpg\">[3]</a> " % vid_id
			out_video += "<a href=\"https://i.ytimg.com/vi/%s/sddefault.jpg\">[4]</a> " % vid_id
			out_video += "<a href=\"https://i.ytimg.com/vi/%s/maxresdefault.jpg\">[5]</a> " % vid_id

			if JSON_KEY_PUBLISHED in vid_meta:
				out_video += "<br />\n<b>Published</b>: %s" % timestamp_to_datestring(vid_meta[JSON_KEY_PUBLISHED])

			if JSON_KEY_ADDED_TIME in video:
				out_video += "<br />\n<b>Added to playlist</b>: %s" % timestamp_to_datestring(video[JSON_KEY_ADDED_TIME])

			if vid_meta_timestamp is not None:
				out_video += "<br />\n<b>Snapshot taken</b>: %s" % timestamp_to_datestring(vid_meta_timestamp)
				if vid_meta_timestamp == dump_time:
					out_video += " (dump time)"

			out_video += "\n</td><td>"

			# description

			if JSON_KEY_DESCRIPTION in vid_meta:
				out_video += add_newlines(sanitize_display_string(vid_meta[JSON_KEY_DESCRIPTION]))

			out_video += "</td></tr>"
			out_table += out_video

		### end table ###
		out_table += "</table>\n"

		out_info += "<br />\n<b>Contents status</b>:"
		for status, count in status_counts.items():
			if count < 1:
				continue
			out_info += "<br />\n%s: %d" % (status, count)

		out_html += out_info
		out_html += out_table
		out_html += "</body>\n</html>\n"

		with open(output_path, "w") as f:
			f.write(out_html)
