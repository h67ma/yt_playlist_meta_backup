import os
import argparse
import shutil
from datetime import datetime

from consts import *
from json_util import load_json, save_json
from html_gen import generate_html
from util import get_file_title_from_path, datetime_to_timestring, datetime_to_timestamp
from yt_api import build_yt_api_object, dump_account_playlists, dump_list_of_playlists


def get_local_db(db_path: str) -> object:
	"""
	If the database file does not exist, creates a database.
	If the database file exists, loads it.
	"""
	db = load_json(db_path)
	if db is None:
		print("Cannot load local database, creating new one")
		return DB_TEMPLATE

	return db


def save_local_db(db: object, db_path: str, backups_dir: str, no_backup: bool, datetime_now: datetime):
	if not no_backup and os.path.exists(db_path):
		db_name = get_file_title_from_path(db_path)
		backup_filename = "%s_%s.json" % (db_name, datetime_to_timestring(datetime_now))
		print("Backing up", db_name, "to", backup_filename)
		os.makedirs(backups_dir, exist_ok=True)
		backup_path = os.path.join(backups_dir, backup_filename)
		shutil.move(db_path, backup_path)
	save_json(db, db_path)


def can_overwrite_snapshot(existing_snapshot: object, new_snapshot: object) -> bool:
	"""
	Checks if a snapshot metadata object can be overwritten with a new one. This can happen if the new one contains the
	same keys with the same values. It can also contain additional, new keys.
	Assumptions: both are dictionaries containing non-array and non-object values.
	"""
	for key, value in existing_snapshot.items():
		if key not in new_snapshot:
			return False
		elif new_snapshot[key] != existing_snapshot[key]:
			return False

	return True


def update_db(db: object, dump: object, timestamp_now: int) -> object:
	for playlist in dump:
		if JSON_KEY_VIDEOS not in playlist:
			print("\"%s\" not found in playlist, skipping" % JSON_KEY_VIDEOS)
			continue

		for in_video in playlist[JSON_KEY_VIDEOS]:
			if JSON_KEY_ID not in in_video:
				print("\"%s\" not found in video, skipping" % JSON_KEY_ID)
				continue

			vid_id = in_video[JSON_KEY_ID]
			del in_video[JSON_KEY_ID] # vid id is a key in db, it's not needed inside meta

			if JSON_KEY_ADDED_TIME in in_video:
				del in_video[JSON_KEY_ADDED_TIME] # added to playlist is stored in dumps, in playlists

			if vid_id in db:
				# at least one version of this video is already present in db
				same_metadata_timestamp = None
				insert_updated = True
				for existing_video_timestamp, existing_video in db[vid_id].items():
					if existing_video_timestamp == timestamp_now:
						# we've already parsed this metadata in some other playlist during this run.
						# it might happen that the metadata is actually different, but if it's from the same-ish time
						# it doesn't really matter which one we take.
						insert_updated = False
						break

					if can_overwrite_snapshot(existing_video, in_video):
						same_metadata_timestamp = existing_video_timestamp
						break

				if insert_updated:
					if same_metadata_timestamp is not None:
						# one of the captures of metadata matches current capture - only bump its time
						# (delete existing and add new with updated timestamp)
						del db[vid_id][existing_video_timestamp]

					# add the new metadata entry either way
					db[vid_id][timestamp_now] = in_video
			else:
				# video is not found in db - add it with current time
				db[vid_id] = {
					timestamp_now: in_video
				}
	return db


if __name__ == "__main__":
	parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
	parser.description = "YouTube playlist metadata archiver tool"
	parser.add_argument("-o", "--oauth", action="store_true", help=("Dump playlists created by a youtube account (OAuth). Can be used alongside -p."))
	parser.add_argument("-p", "--playlists", action="store_true", help=("Dump playlists from a list of playlists contained in a file ($ROOT_DIR/" + FILENAME_SAVED_PLAYLISTS + "). The file should contain links or playlist IDs, separated by newline. Can be used alongside -a."))
	parser.add_argument("--html", action="store", type=str, help=("Path to an existing dump file. Instead of dumping playlists, generate HTML files for that file."))
	parser.add_argument("--root", action="store", type=str, default=DEFAULT_ROOT, help=("Root data directory path"))
	parser.add_argument("--nothumbs", action="store_true", help=("Don't download thumbnails"))
	parser.add_argument("--nobackup", action="store_true", help=("Don't make a backup of local database before modification"))
	args = parser.parse_args()

	if args.html is not None:
		print("HTML mode")

		if args.oauth or args.playlists:
			print("--oauth and --playlists cannot be used alongside --html")
			exit(1)

		dump = load_json(args.html)
		if dump is None:
			print("Cannot load dump file")
			exit(1)

		db_path = os.path.join(args.root, FILENAME_DB)
		output_filename = os.path.join(args.root, DIR_HTML, get_file_title_from_path(args.html))
		thumbs_dir_path = os.path.join(args.root, DIR_THUMBS)

		db = get_local_db(db_path)

		generate_html(db, dump, output_filename, thumbs_dir_path)

		print("HTML generation finished")
	else:
		print("Dump mode")

		if not args.oauth and not args.playlists:
			print("--oauth and/or --playlists must be selected in dump mode")
			exit(1)

		youtube_api = build_yt_api_object()

		db_path = os.path.join(args.root, FILENAME_DB)
		backups_dir_path = os.path.join(args.root, DIR_BACKUPS)
		thumbs_dir_path = os.path.join(args.root, DIR_THUMBS)
		dumps_dir_path = os.path.join(args.root, DIR_DUMPS)
		saved_playlists_path = os.path.join(args.root, FILENAME_SAVED_PLAYLISTS)

		db = get_local_db(db_path)

		time_now = datetime.now()

		if args.oauth:
			full_dump_oauth, refs_dump_oauth = dump_account_playlists(youtube_api, thumbs_dir_path, args.nothumbs, time_now)
			save_json(refs_dump_oauth, os.path.join(dumps_dir_path, "dump_%s_account.json" % datetime_to_timestring(time_now)))
			db = update_db(db, full_dump_oauth, datetime_to_timestamp(time_now))
			save_local_db(db, db_path, backups_dir_path, args.nobackup, time_now)

		if args.playlists:
			full_dump_oauth, refs_dump_oauth = dump_list_of_playlists(youtube_api, thumbs_dir_path, args.nothumbs, time_now, saved_playlists_path)
			if full_dump_oauth is None or refs_dump_oauth is None:
				print("Dump aborted")
				exit(1)
			save_json(refs_dump_oauth, os.path.join(dumps_dir_path, "dump_%s_saved.json" % datetime_to_timestring(time_now)))
			db = update_db(db, full_dump_oauth, datetime_to_timestamp(time_now))
			save_local_db(db, db_path, backups_dir_path, args.nobackup, time_now)

		print("Dump finished")
