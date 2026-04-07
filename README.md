# Teepee

The simple, speedy Telegram client with the blind in mind.

## Introduction

Teepee is a lightweight desktop Telegram client built with wxPython and designed with blind and visually impaired users in mind. If you want a Telegram experience that works smoothly with screen readers, supports keyboard navigation throughout, and doesn't try to get in the way of everything, Teepee is for you.

## Features

- Send and receive text messages, voice messages, and media.
- Browse your chat list with a live search filter.
- Reply to, delete, and manage messages with keyboard shortcuts.
- Record and send voice messages directly from the app.
- Play received voice messages inline.
- Join, leave, and manage groups and channels, including viewing members, kicking users, and editing group titles.
- Interact with bot inline buttons for bots that support it.
- Start voice calls with contacts.
- Notification sounds for sent messages, received messages, group messages, and channel messages, with a setting to toggle them on or off.
- Configure audio input and output devices from the settings dialog.
- All on-screen elements, such as buttons, text fields, and lists, are clearly labelled for screen reader users.
- Keyboard friendly navigation with tab, arrow keys, and area shortcuts (Ctrl+1 for chat list, Ctrl+2 for messages, Ctrl+3 for message input).
- A Keyboard Shortcuts reference available from the Help menu or by pressing F1.
- Detects if your system is in dark mode and applies a dark theme to suit, including dark title bars on Windows.

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

Teepee needs a Telegram API ID and Hash to connect. Official Teepee builds already have these credentials built in, but if credentials are not embedded in your own custom build, the app will prompt you to enter them on first launch.

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

1. Select a chat from the chat list on the left, or press the New Chat button to start a conversation with a user by username or phone number.
2. Type your message in the message input field at the bottom.
3. Press Enter to send, or Shift+Enter to add a new line.

### Voice messages

1. Press the Voice button to start recording.
2. Press the Stop button (the same button) to stop recording and send the voice message.
3. To play a received voice message, select it in the message list and press the Play button.

### Keyboard shortcuts

The following shortcuts are available throughout the app. You can also view this list by pressing F1 or opening Help then Keyboard Shortcuts.

The following table lists all keyboard shortcuts grouped by category.

| Shortcut | Action |
|----------|--------|
| Ctrl+1 | Focus chat list |
| Ctrl+2 | Focus message list |
| Ctrl+3 | Focus message input |
| Enter | Send message (when in the input field) |
| Shift+Enter | New line in message |
| Ctrl+R | Reply to selected message |
| Escape | Cancel reply |
| Delete | Delete selected message or chat |
| Ctrl+Shift+C | Start voice call |
| Ctrl+Shift+H | Hang up |
| Ctrl+, | Audio settings |
| F1 | Keyboard shortcuts |
| Ctrl+Q | Exit |

### Group management

From the Group menu you can:

- Join a group or channel by username or invite link.
- Leave the currently selected group or channel.
- View the member list.
- Kick a member by username.
- Edit the group title.

### Settings

Press Ctrl+, or open the Settings menu to configure audio input and output devices and toggle notification sounds.
