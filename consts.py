DEFAULT_ROOT = "yt_meta_dump"
FILENAME_DB = "db.json"
FILENAME_SAVED_PLAYLISTS = "saved_playlists.txt"
DIR_BACKUPS = "backups"
DIR_DUMPS = "dumps"
DIR_HTML = "html"
DIR_THUMBS = "thumbs"

DB_TEMPLATE = {}

JSON_KEY_PLAYLISTS = "playlists"
JSON_KEY_TITLE = "title"
JSON_KEY_VIDEOS = "videos"
JSON_KEY_ID = "id"
JSON_KEY_CHANNEL_NAME = "channelName"
JSON_KEY_CHANNEL_USERNAME = "channelUsername"
JSON_KEY_CHANNEL_ID = "channelId"
JSON_KEY_STATUS = "status"
JSON_KEY_DESCRIPTION = "description"
JSON_KEY_DUMP_TIME = "dumpTime"
JSON_KEY_ADDED_TIME = "addedToPlaylist"
JSON_KEY_PUBLISHED = "published"
JSON_KEY_DURATION = "duration"

STATUS_PRIVATE = "private"
STATUS_UNSPEC = "privacyStatusUnspecified"
STATUS_PUBLIC_OR_UNLISTED = "publicOrUnlisted"
STATUS_UNLISTED = "unlisted"
STATUS_PUBLIC = "public"

KNOWN_STATUSES = [
	STATUS_UNSPEC,
	STATUS_PRIVATE,
	STATUS_UNLISTED,
	STATUS_PUBLIC,
	STATUS_PUBLIC_OR_UNLISTED,
]