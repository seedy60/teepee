# Teepee

The simple, speedy Telegram client with the blind in mind.

## Introduction

Teepee is a lightweight desktop Telegram client designed with blind and visually impaired users in mind. If you want a Telegram experience that works smoothly with screen readers, supports keyboard navigation throughout, and doesn't try to get in the way of everything, Teepee is for you.

## Features

### Messaging

- Send and receive text messages, voice messages, files, and media.
- Messages open in a separate window when you select a chat, keeping the chat list always visible.
- Browse your chat list with a live search filter.
- Reply to, edit, delete, and manage messages with keyboard shortcuts.
- Edit your own sent text messages with Ctrl+E.
- Copy a message to the clipboard with Ctrl+C when the message list is focused.
- When deleting a message or chat, choose whether to delete for yourself only or for everyone.
- Record and send voice messages directly from the app.
- Send files using the Attach button or Ctrl+Shift+A.
- Play received voice messages and audio files inline.
- Play received video files in your default media player.
- Download and save voice messages, photos, videos, audio files, and document attachments using the Save button or Ctrl+Shift+S.
- Media types (audio, video, sticker, GIF, document) are clearly labelled in the message list and chat previews.
- Interact with bot inline buttons for bots that support it.
- Unread message counts are shown in the chat list and cleared automatically when you open a chat.
- Message timestamps are displayed in your local timezone.
- Choose between 12-hour and 24-hour time format in Settings.
- Click the Open Link button to open URLs contained in a message. If a message contains multiple URLs, a list lets you choose which one to open.

### Files browser

- Groups and channels have a Files tab that lists all shared documents.
- Search files by name with server-side search.
- Download files directly from the file list.
- Load more to fetch older files.

### Calls

- Start voice calls with contacts using Ctrl+Shift+C.
- Start video calls with contacts using Ctrl+Shift+V. If the camera fails, the call falls back to voice automatically.
- Hang up with Ctrl+Shift+H.
- Mute and unmute your microphone during a call.
- Incoming calls show a dialog with Accept and Decline buttons. Both voice and video calls are supported.

### Account management

- View and edit your full Telegram account from File then My Account, including:
  - Profile: first name, last name, username, phone (read-only), bio, birthday (with optional year), and profile photos (upload or delete).
  - Privacy: control who can see your last seen, phone number, profile photo, forwarded messages, calls, group invites, and birthday (everyone, contacts only, or nobody).
  - Security: view two-factor authentication status, list all active sessions, and terminate any session remotely.
  - Account: set the self-destruct timer (1, 3, 6, or 12 months of inactivity before automatic deletion).

### Chat muting

- Mute chat notifications temporarily (1 hour, 8 hours, 1 day, 1 week) or permanently.
- Muted chats are labelled [Muted] in the chat list and produce no notification sounds.
- Mute and unmute from the Chat menu or the right-click context menu on the chat list.
- The context menu disables the Unmute option when the chat is not muted.

### Group management

- Create a new group and optionally invite members at creation time.
- Create a new channel with an optional description.
- Invite a user to the currently selected group or channel by username.
- Join a group or channel by username or invite link.
- Leave the currently selected group or channel.
- View the member list.
- Kick a member by username.
- Edit the group title.

### Sound packs

Teepee plays notification sounds for sent messages, received messages, group messages, and channel messages. The sounds are organised into packs.

- The default pack ships in the sounds/default folder with four WAV files: sent.wav, received.wav, group_received.wav, and channel_received.wav.
- To create a custom sound pack, add a new folder inside sounds/ with the same four filenames. For example, sounds/retro/ with your own WAV files.
- Select your preferred pack from the Settings dialog (Ctrl+,) under Notifications then Sound Pack.
- Toggle all notification sounds on or off with the "Enable notification sounds" checkbox in the same section.

### Accessibility

- All on-screen elements - buttons, text fields, lists, and dialogs - are clearly labelled for screen reader users.
- Keyboard-friendly navigation with Tab, arrow keys, and area shortcuts (Ctrl+1 for chat list, Ctrl+2 for messages, Ctrl+3 for message input, Ctrl+4 for files list, Ctrl+5 for file search).
- Focus is managed throughout the app: after closing dialogs, deleting messages, switching chats, and restoring from the system tray, focus returns to a logical target.
- Status messages are mirrored to both the main window and message window, so screen reader users always get feedback regardless of which window has focus.
- A Keyboard Shortcuts reference is available from the Help menu or by pressing F1.
- Dark mode detected automatically with a matching dark theme applied, including dark title bars on Windows.
- High contrast mode is detected and respected.
- Automatic update checking on launch with a manual Check for Updates option in the Help menu.
- System tray integration: closing the window minimises to tray; a balloon notification confirms.
- Right-click context menu on the chat list for quick access to mute, unmute, and delete actions.

## Installation

### From source

Teepee uses [UV](https://docs.astral.sh/uv/), a fast, modern package manager for Python written in Rust.

The following instructions detail how to download and run Teepee from its source code on Windows.

1. Press Windows + R, type powershell and hit enter.
2. Install UV.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

3. Use UV to install Python if it is not already installed.

```
uv python install
```

4. Clone the repository and switch to its directory.

```
git clone https://github.com/seedy60/teepee.git
cd teepee
```

5. Install the required libraries.

```
uv sync
```

6. Run the program.

```
uv run python run.py
```

### Pre-compiled

1. [Download the latest release](https://github.com/seedy60/teepee/releases/latest/download/Teepee.zip).
2. Extract the zip file with your zip archiver of choice.
3. Navigate to the extracted Teepee folder and run Teepee.exe. If file extensions don't show on your system, the filename will just be Teepee.

## Compiling

Run the build script to generate the Windows executable and a zip archive ready for distribution.

```
uv run python build.py
```

The output is placed in the dist folder.

## Telegram API credentials

Teepee needs a Telegram API ID and API Hash to connect. If credentials are not already embedded in your own custom build, the app will prompt you to enter them on first launch.

To get your own credentials:

1. Visit [my.telegram.org/apps](https://my.telegram.org/apps) and sign in with your phone number.
2. Create a new application and note the API ID and API Hash.
3. Enter them when prompted by Teepee, or run the credential setup script to embed them for distribution:

```
uv run python setup_credentials.py
```

## Usage

### Signing in

1. Run the program. If API credentials are not set, you will be prompted to enter them.
2. Enter your phone number with country code (for example, +1234567890).
3. Enter the verification code sent to your Telegram account.
4. If you have two-factor authentication enabled, enter your 2FA password when prompted.

### Sending messages

1. Select a chat from the chat list. A separate message window opens with the conversation.
2. Type your message in the message input field at the bottom of the message window.
3. Press Enter to send, or Shift+Enter to add a new line.

### Voice messages and media

1. Press the Voice button to start recording.
2. Press the Stop button (the same button) to stop recording and send the voice message.
3. To play a received voice message or audio file, select it in the message list and press the Play button. Audio plays inline.
4. To play a received video, select it and press the Play button. The video opens in your default media player.
5. To save a voice message, photo, video, audio file, or document, select the message and press the Save button or use Ctrl+Shift+S. Choose where to save the file in the file picker.

### Sending files

1. Open a chat.
2. Press the Attach button, or use Ctrl+Shift+A.
3. Choose a file from the file picker. The file is sent to the current chat.

### Keyboard shortcuts

The following shortcuts are available throughout the app. You can also view this list by pressing F1 or opening Help then Keyboard Shortcuts.

The following table lists all keyboard shortcuts grouped by category.

| Shortcut | Action |
|----------|--------|
| Ctrl+1 | Focus chat list |
| Ctrl+2 | Focus message list |
| Ctrl+3 | Focus message input |
| Ctrl+4 | Focus files list (groups and channels) |
| Ctrl+5 | Focus file search (groups and channels) |
| Enter | Send message (when in the input field) |
| Shift+Enter | New line in message |
| Ctrl+R | Reply to selected message |
| Ctrl+E | Edit selected sent message |
| Ctrl+C | Copy selected message to clipboard (in message list) |
| Ctrl+Shift+A | Attach and send a file |
| Ctrl+Shift+S | Save the selected voice message or file attachment |
| Escape | Cancel reply |
| Delete | Delete selected message or chat (choose delete for me or for everyone) |
| Ctrl+Shift+C | Start voice call |
| Ctrl+Shift+V | Start video call |
| Ctrl+Shift+H | Hang up |
| Ctrl+, | Settings |
| F1 | Keyboard shortcuts |
| Alt+F4 | Minimize to system tray |
| Ctrl+Q | Quit |

### Group management

From the Group menu you can:

- Create a new group. You will be prompted for a name and optionally a comma-separated list of usernames to invite.
- Create a new channel. You will be prompted for a name and an optional description.
- Invite a user to the currently selected group or channel by entering their username.
- Join a group or channel by username or invite link.
- Leave the currently selected group or channel.
- View the member list.
- Kick a member by username.
- Edit the group title.

### Settings

Press Ctrl+, or open the Settings menu to configure:

- Audio input and output devices.
- Camera device for video calls.
- Notification sounds on or off.
- Sound pack selection (see the Sound packs section above for how to create custom packs).
- Time format: choose between 12-hour (1:30 PM) and 24-hour (13:30) display.

### Account

Open File then My Account to view and edit your Telegram account. The dialog has four tabs:

- **Profile** - edit your first name, last name, username, and bio. Phone number is displayed as a read-only field. Set or clear your birthday with an optional year. Upload a new profile photo or delete your current one.
- **Privacy** - choose who can see your last seen, phone number, profile photo, forwarded messages, calls, group invites, and birthday.
- **Security** - view your two-factor authentication status, see all active sessions, and terminate any session remotely.
- **Account** - set the self-destruct timer for your account.

### Chat muting

To mute a chat, select it in the chat list and choose Chat then Mute Chat from the menu bar, or right-click the chat and select Mute Chat. Pick a duration: 1 hour, 8 hours, 1 day, 1 week, or permanently. Muted chats show a [Muted] label in the chat list and will not play notification sounds for incoming messages.

To unmute, select the chat and choose Chat then Unmute Chat, or right-click and select Unmute Chat.
