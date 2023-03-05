# ChatGPT Discord Bot

<p align="center">
  <a href="https://github.com/EcmaXp/chatgpt-discord-bot/releases"><img src="https://img.shields.io/github/v/release/EcmaXp/chatgpt-discord-bot"></a>
  <a href="https://github.com/EcmaXp/chatgpt-discord-bot/commits/main"><img src="https://img.shields.io/github/last-commit/EcmaXp/chatgpt-discord-bot"></a>
  <a href="https://github.com/EcmaXp/chatgpt-discord-bot/blob/main/LICENSE.md"><img src="https://img.shields.io/github/license/EcmaXp/chatgpt-discord-bot"></a>
  <a href="https://github.com/EcmaXp/chatgpt-discord-bot"><img src="https://img.shields.io/github/languages/code-size/EcmaXp/chatgpt-discord-bot"></a>
  <a href="https://conventionalcommits.org/en/v1.0.0/"><img src="https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white"></a>
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

## How to download it

* Clone/Download the repository
    * To clone it and get the updates you can definitely use the command
      `git clone`
* Create a discord bot [here](https://discord.com/developers/applications)
* Get your bot token
* Invite your bot on servers using the following invite:
  https://discord.com/oauth2/authorize?&client_id=YOUR_APPLICATION_ID_HERE&scope=bot+applications.commands&permissions=PERMISSIONS (
  Replace `YOUR_APPLICATION_ID_HERE` with the application ID and replace `PERMISSIONS` with the required permissions
  your bot needs that it can be get at the bottom of a this
  page https://discord.com/developers/applications/YOUR_APPLICATION_ID_HERE/bot)

## How to set up

To set up the bot I made it as simple as possible. I now created a [config.example.json](config.example.json) file where you can put the
needed things to edit.

Here is an explanation of what everything is:

| Variable                  | What it is                                                  |
|---------------------------|-------------------------------------------------------------|
| YOUR_BOT_PREFIX_HERE      | The prefix you want to use for normal commands              |
| YOUR_BOT_TOKEN_HERE       | The token of your bot                                       |
| YOUR_BOT_PERMISSIONS_HERE | The permissions integer your bot needs when it gets invited |
| YOUR_APPLICATION_ID_HERE  | The application ID of your bot                              |
| YOUR_OPENAI_API_KEY_HERE  | The API key of your OpenAI account                          |
| OWNER_GUILD_ID            | The guild ID of the guild where the bot owners are          |
| OWNERS                    | The user ID of all the bot owners                           |
| OPENAI_CHATGPT_MODEL      | The model you want to use for the ChatGPT                   |
| CHATGPT_ALLOW_MENTION     | Whether or not you want to allow mentions in the ChatGPT    |

## How to start

To start the bot you simply need to launch, either your terminal (Linux, Mac & Windows), or your Command Prompt (Windows).

Before running the bot you will need to install all the requirements with this command:

```
python -m pip install -r requirements.txt
```

After that you can start it with

```
python bot.py
```

> **Note** You may need to replace `python` with `py`, `python3`, `python3.11`, etc. depending on what Python versions you have installed on the machine.

## Issues or Questions

If you have any issues or questions, you can post them [here](https://github.com/EcmaXp/chatgpt-discord-bot/issues).

## Versioning

We use [SemVer](http://semver.org) for versioning. For the versions available, see
the [tags on this repository](https://github.com/EcmaXp/chatgpt-discord-bot/tags).

## Built With

* [Python 3.9.12](https://www.python.org/)
* [kkrypt0nn/Python-Discord-Bot-Template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details

Also, [chatgpt_discord_bot/cogs/chatgpt.py](chatgpt_discord_bot/cogs/chatgpt.py) is owned by [EcmaXp](https://github.com/EcmaXp) and is licensed under the Apache License 2.0

And, this project forked from [kkrypt0nn/Python-Discord-Bot-Template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template):
- Keep the credits, and a link to this repository in all the files that contains [my](https://github.com/kkrypt0nn) code
- Keep the same license for unchanged code
