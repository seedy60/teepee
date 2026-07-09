# Teepee

The simple, speedy Telegram client with the blind in mind.
Teepee is a lightweight desktop Telegram client for Windows that puts blind and visually impaired users first. It pairs a graphical user interface (GUI) that is easy to navigate with a keyboard with on-screen elements that are clearly labelled for screen readers such as [NVDA](https://nvaccess.org/about-nvda/) and [JAWS](https://www.freedomscientific.com/products/software/jaws/). Notification sounds, screen reader announcements through Prism, dark mode, and a fully customisable message presentation are also included.

## Teepee features

Teepee is a fully-featured Telegram client. You can send and receive text messages, voice notes, stickers, files and media, place voice and video calls, manage your account, create and run groups and channels, browse files and links shared in any chat, get AI descriptions of images and videos that arrive without a caption, and customise just about everything that affects what you hear and what you see. The chat list and message list live in separate windows so the chat list never disappears when you open a conversation.

## Running Teepee

### from source

Teepee is written in Python and uses [UV](https://docs.astral.sh/uv/), a fast, modern Python package manager written in Rust. You will also need [Git for Windows](https://gitforwindows.org/) installed. These instructions apply to the Windows operating system.

1. Press Windows + R, type powershell, and press Enter to launch PowerShell.
2. Install UV.
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
3. Use UV to install Python if it is not already installed.
```
uv python install
```
4. Clone this repository with git by running the following command.
```
git clone https://github.com/seedy60/teepee.git
```
5. Move into the Teepee folder and install the libraries needed for Teepee.
```
cd teepee
uv sync
```
6. Run Teepee.
```
uv run python run.py
```

### Compiled.

If you just want a pre-compiled binary without having to fight with Python, you can [download the latest release here](https://github.com/seedy60/teepee/releases/latest/download/Teepee.zip). To run this, simply extract the zip file and run Teepee.exe. If file extensions don't show on your system, the filename will just be Teepee.
The pre-compiled Teepee binary runs on Windows 10 and higher.

## Telegram API credentials

Teepee needs a Telegram API ID and API Hash to connect. Official Teepee builds already have these baked in. If your build does not have credentials embedded, the app will prompt you to enter them on first launch.

To get your own credentials:

1. Visit [my.telegram.org/apps](https://my.telegram.org/apps) and sign in with your phone number.
2. Create a new application and note the API ID and API Hash.
3. Enter them when prompted by Teepee, or run setup_credentials.py to embed them into a build for distribution.
```
uv run python setup_credentials.py
```

## Signing in to Telegram

When you launch Teepee for the first time, you will be greeted with a sign-in dialog.

1. Enter your phone number including country code, E.G. +1234567890.
2. Tab to the Continue button and press Space or Enter.
3. Telegram will send you a verification code through another Telegram client or by SMS. Enter the code in the next dialog and press Enter.
4. If you have two-factor authentication enabled, enter your 2FA password when prompted.

Your session is stored inside the Teepee folder in your AppData directory. If you ever need to sign out, choose File then Sign Out and Teepee will clear your session and return you to the sign-in screen.

## Sending messages

Once signed in, you will land on the chat list, which shows your conversations with a live search filter at the top. Use the up and down arrow keys to move through the list, or type to filter.

1. Select a chat from the chat list and press Enter. A separate message window opens with the conversation.
2. Type your message in the message input field at the bottom of the message window.
3. Press Enter to send, or Shift + Enter to add a new line.

To reply to a message, select it in the message list and press Control + R. To see which message a reply is pointing to, select the reply and press Control + Shift + Semicolon; Teepee will read the original out in a dialog, fetching it from Telegram if it is older than the messages currently loaded. To edit one of your own sent text messages, press Control + E. To copy a message to the clipboard, press Control + C while the message list is focused. To delete a message or chat, press Delete and choose whether to delete it for yourself only or for everyone.

If a message contains a link, an Open Link button appears in the message actions. Press it to open the URL in your default browser. If a message contains more than one link, a list dialog lets you choose which one to open.

Unread message counts are shown in the chat list and cleared automatically when you open a chat. Message timestamps are displayed in your local timezone. Recent messages show just the time; messages older than 24 hours include the full date, E.G. Friday, April 17th, 2026 at 13:30.

## Voice messages and media

1. Press the Voice button to start recording.
2. Press the Stop button (the same button) to stop recording and send the voice message.
3. To play a received voice message or audio file, select it in the message list and press the Play button. Audio plays in-client.
4. To play a received video, select it and press the Play button. The video opens in your default media player.
5. To save a voice message, photo, video, audio file, or document, select the message and press the Save button or use Control + Shift + S. Choose where to save the file in the file picker.

Media types such as audio, video, picture, sticker, GIF, and document are clearly labelled in the message list and chat previews so you always know what kind of attachment you are looking at.

## Sending files and stickers

To send a file, press the Attach button or Control + Shift + A. Pick a file and add an optional caption that doubles as alt text for those who are blind/visually impaired, deaf/hard of hearing etc.

To send a sticker, press the Sticker button. Search for a sticker by typing text (E.G. "cat", "smile") or an emoji, then choose one from the results and press Enter.

## Calls

To start a voice call with the selected chat, press Control + Shift + C. To start a video call, press Control + Shift + V. If your camera fails the call will fall back to voice automatically. To hang up at any time, press Control + Shift + H. You can mute and unmute your microphone during a call from the in-call dialog.

## Message presentation

Teepee lets you control exactly how each message is presented in a chat. Open the settings dialog with Control + comma and look under Display for the Message Template field. The following placeholders are supported:

* [user]: the user who sent the message.
* [msg]: the content of the message.
* [ftype]: if a message contains media, the file type of the attachment.
* [fname]: if a message contains media, the name of the attached file.
* [fsize]: if a message contains media, the size of the attached file.
* [datetime]: the time or date the message was sent depending on how long ago it was sent. If it was sent more than 24 hours ago, the exact date and time will be shown.
* [seen]: the sent/seen status of the message.

For example, you might use a template like this:

[user]: [msg] sent at [datetime].

If you want to start over, press the Reset Template to Default button next to the field. The default template is "[msg], [user] at [datetime] [seen]", which produces output similar to "Hello, Alice at 13:45" for incoming messages and "Hi, You at 13:46 Seen" for messages you have sent that have been read.

## File browser

Every chat -- one-on-one user chats as well as groups and channels -- has a Files tab that lists every document shared in the conversation. Search by name with server-side search, download files directly from the list, or press Load More to fetch older files. Use Control + 4 to focus the file list and Control + 5 to focus the file search.

## Links

Every chat, group, and channel has a Links tab that lists every link and URL shared in the conversation, newest first, along with who sent each one and when. This includes plain links, links hidden behind link text, and links from web page previews. Select a link and press Enter, double-click it, or press the Open button to open it in your default browser. Press Control + C or the Copy button to copy the selected link to the clipboard. Press Load More to fetch older links. Use Control + 6 to jump straight to the links list.

## AI media descriptions

Teepee can ask Google Gemini to describe an image or video for you, which is handy when someone sends a picture or clip with no caption (or a useless one like "pic"). Select the message and press the Describe button in the message actions, or press Control + Shift + D. A dialog opens immediately announcing that the request is in flight, so your screen reader confirms the action even if Teepee's spoken announcements are turned off; a Cancel button lets you dismiss it while the request is running. When Gemini responds, the same dialog updates in place with the description (or an error explanation) and a Copy button so you can put it on the clipboard. The Describe button is available for any image or video, even ones that already have a caption.

This feature needs a Google Gemini API key, which you can get for free from [Google AI Studio](https://aistudio.google.com/apikey). Open the settings dialog with Control + comma, find the AI descriptions section, and paste your key into the Gemini API key field. Your key is stored securely in your operating system's credential store (Windows Credential Locker, macOS Keychain, or the Linux Secret Service) rather than in Teepee's config file. Until a key is set, Teepee will remind you where to add one. Images and short videos up to about 14 MB are supported; larger files are skipped to keep requests fast. Media is downloaded and sent to Google's Gemini API only when you press Describe.

Below the key field is a Model dropdown. When you open Settings with a key already saved, Teepee automatically fetches the current list of models available to your key from Google and fills the dropdown, newest first, so the latest models always show up without any extra steps. Before that fetch finishes (or if you have no key yet) it shows a short built-in list, with gemini-2.5-flash as the fast, inexpensive default. You can also type any model name, or press Refresh models to fetch the list again (for example after pasting a new key).

## Account

Open File then My Account to view and edit your full Telegram account. The dialog has four tabs:

* Profile: edit your first name, last name, username, and bio. Phone number is displayed as a read-only field. Set or clear your birthday with an optional year. Upload a new profile photo or delete your current one.
* Privacy: choose who can see your last seen, phone number, profile photo, forwarded messages, calls, group invites, and birthday (everyone, contacts only, or nobody).
* Security: view your two-factor authentication status. Set up a 2FA password if you don't already have one, change an existing password, or disable 2FA entirely; each option opens a sub-dialog that asks for the password fields it needs and an optional hint. You can also supply a recovery email when setting up or changing the password; Telegram will send a verification code to that address that Teepee will prompt you for in a follow-up dialog. The Security tab also lists all your active sessions and lets you terminate any one of them remotely.
* Account: set the self-destruct timer for your account (1, 3, 6, or 12 months of inactivity before automatic deletion).

## Group management

From the Group menu you can:

* Create a new group. You will be prompted for a name, private or public visibility, a public username for public groups, and optionally a comma-separated list of usernames to invite.
* Create a new channel. You will be prompted for a name, optional description, private or public visibility, and a public username for public channels.
* Invite a user to the currently selected group or channel by entering their username.
* Join a group or channel by username or invite link.
* Generate an invite link for the currently selected group or channel and copy it to the clipboard.
* Leave the currently selected group or channel.
* View the member list, including role labels (Owner, Admin, Member).
* Promote a member to admin or remove the admin role from the member list dialog. When promoting to admin in a supergroup or channel, you can also tick "Post anonymously" so their messages appear as coming from the group or channel itself rather than from their user account; their other admin permissions are preserved unchanged.
* Change per-member send permissions in channels and supergroups directly from the member list dialog.
* Kick members directly from the member list dialog or by username.
* Edit the group title.

Note: Telegram public usernames must be available and not collectible usernames. Per-member permission editing is available for channels and supergroups; basic groups do not expose the same granular permission model.

## Chat muting

To mute a chat, select it in the chat list and choose Chat then Mute Chat from the menu bar, or right-click the chat and select Mute Chat. Pick a duration: 1 hour, 8 hours, 1 day, 1 week, or permanently. Muted chats show a [Muted] label in the chat list and will not play notification sounds for incoming messages.

To unmute, select the chat and choose Chat then Unmute Chat, or right-click and select Unmute Chat.

## Blocking and reporting

To block a user, select their chat and choose Chat then Block User, or right-click and select Block User. Blocked users cannot send you messages or calls.

To unblock, choose Chat then Unblock User, or right-click and select Unblock User.

To report a user, choose Chat then Report User. Select a reason from the list (spam, violence, pornography, child abuse, illegal drugs, personal details shared, fake account, or other) and optionally provide additional details. These options are only available for one-on-one user chats.

## Notifications and the system tray

Closing the main window minimizes Teepee to the system tray rather than quitting the program, and a balloon notification confirms the move. While Teepee is in the tray (or just minimized), system notifications appear when a new message arrives. Notifications include the sender name, the chat type (chat, group, or channel), and a message preview. Muted chats do not produce notifications. You can turn this behaviour on or off in the settings dialog under Notifications with the "Show notifications when minimized" checkbox.

Teepee also detects dark mode and high contrast mode automatically and applies a matching theme, including dark title bars on Windows. Teepee checks for updates on launch, and you can also choose Help then Check for Updates at any time.

## Settings

Press Control + comma or open the Settings menu to configure:

* Audio input and output devices, with Test Speaker and Test Microphone buttons to make sure everything is working.
* Camera device for video calls.
* Notification sounds on or off.
* Screen reader announcements on or off (off by default).
* Announcement backend selection: automatic best backend or a specific Prism backend.
* Announcement voice selection for the selected backend, when voice selection is supported.
* Show notifications when minimized on or off.
* Sound pack selection (see the sound packs section below for how to create custom packs).
* Time format: choose between 12-hour (1:30 PM) and 24-hour (13:30) display.
* Number of chats to load (10 to 500, default 100).
* Number of messages to load per chat (10 to 500, default 50).
* Message template (see the message presentation section above).
* Gemini API key for AI media descriptions (see the AI media descriptions section above).

## Sound packs

### What are sound packs?

Sound packs are collections of sounds that Teepee uses to indicate user actions and program events such as a sent message, a received message, a group message, a channel message, an incoming call, an outgoing call, a sent reply, and a received reply. In terms of structure, a sound pack is essentially a folder with wave files inside of it.

### Creating and adding sound packs

You can use the default sound pack as a basis when creating your own sound packs. The default pack ships in the sounds/default folder with these ten wave files: sent.wav, received.wav, group_received.wav, channel_received.wav, call_in.wav, call_out.wav, reply_sent.wav, voice_start.wav, voice_stop.wav, and reply_received.wav. To add a sound pack, create a new folder inside Teepee's sounds folder, E.G. sounds/retro, and add your wave files into the folder using the same filenames. Be sure to check your filenames against the default folder, otherwise your sounds might not play.

### Changing sound packs.

You can change sound packs by doing the following:

1. Press Control + comma to open the settings dialog.
2. Choose the sound pack you want from the Sound Pack dropdown under Notifications, tab to the OK button and press either Space or Enter.

The new pack takes effect immediately. No restart needed.

## Keyboard shortcuts

The following table lists the keyboard shortcuts that work throughout Teepee. You can also view this list at any time by pressing F1 or opening Help then Keyboard Shortcuts.

| Shortcut | Action |
|----------|--------|
| Control + 1 | Focus chat list |
| Control + 2 | Focus message list |
| Control + 3 | Focus message input |
| Control + 4 | Focus files list (groups and channels) |
| Control + 5 | Focus file search (groups and channels) |
| Control + 6 | Focus links list |
| Enter | Send message (when in the input field) |
| Shift + Enter | New line in message |
| Control + R | Reply to selected message |
| Control + Shift + Semicolon | Show the message a reply is replying to |
| Control + E | Edit selected sent message |
| Control + C | Copy selected message to clipboard (in message list) |
| Control + Shift + A | Attach and send a file |
| Control + Shift + S | Save the selected voice message or file attachment |
| Control + Shift + D | Describe the selected image or video with Gemini |
| Escape | Cancel reply |
| Delete | Delete selected message or chat (choose delete for me or for everyone) |
| Control + Shift + C | Start voice call |
| Control + Shift + V | Start video call |
| Control + Shift + H | Hang up |
| Control + comma | Settings |
| F1 | Keyboard shortcuts |
| Alt + F4 | Minimize to system tray |
| Control + Q | Quit |

## Compiling

Use the following build script to generate a Windows executable and a zip archive ready for distribution.

```
uv run python build.py
```

The output is placed in the `dist` folder.

## Debugging

Teepee writes debug logs to a file in the user's data directory:
- Windows: `%APPDATA%\Teepee\logs\teepee.log`
- Linux: `~/.config/Teepee/logs/teepee.log`