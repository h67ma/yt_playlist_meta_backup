# YouTube playlist & video metadata archiver tool

## Motivation
Because videos are deleted/privated all the time, users might find that they have previously added some video to a playlist, only to later find it deleted/privated, without any indication what exactly was in that video, not even a title or channel name. This is why, in addition to backing up videos themselves, it is important to regularly backup video metadata. With such backup, user would be able to determine what a given video used to be, and could then search for a reupload if needed.

## Operation
This tool does **not** download videos. It uses the freely available YouTube API to query playlists (selected either by taking all playlists created by logged in account, or via a list of playlist IDs). It then saves relevant information to local files (along with thumbnails, optionally). To avoid data duplication, most of the data is saved to a local database (json file). Playlists are saved simply as a list of video ids and date added values, rest is in the database.

With a dump created, it is possible to generate html rendition of each playlist present in the dump. What's important is that if a certain video is no longer available (deleted/privated), all its data will be displayed in html as long as that information was gathered at some point (in a previous dump) as it can be taken from local database.

Note that video metadata might change over time (e.g. the uploader edits video title). Because of that, the local database entries might contain several revisions ("snapshots") of each video metadata. If during making a new backup the metadata differs in any way, a new snapshot will be saved (except the case when only additional key-value pairs are added). If metadata matches the old values, the datetime of that old metadata will be bumped.

Thumbnails can optionally be downloaded, which can be a great help when searching for a reupload of a deleted video. Thumbnails are shared between dumps. Note that a thumbnail will *not* be downloaded again if it already exists, therefore it might not be up to date.

## Included metadata
The following information is saved:

* Playlist
	* Link to playlist
	* Title
	* Description
	* Visibility status
	* Playlist author channel name
	* Link to playlist author channel
* Video
	* Link to video
	* Title
	* Description
	* Channel name
	* Link to channel
	* Visibility status
	* Date of publication
	* Date of addition to playlist
	* Thumbnail (highest possible resolution) (optional)

## API access
To use the tool, it is required to create a YT developer account, create a project, create a client for desktop, and save the secret file to `secret.json`. See https://developers.google.com/youtube/v3/getting-started for instructions.
