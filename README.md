# The bot is currently not working

For this [REASON](https://github.com/brodo97/NotifyMeSenpai/issues/13). If you know how to fix it, post a comment! 


# NotifyMeSenpai
is a useful Telegram bot to stay up to date with your favourite nhentai Artists, Parodies, Tags,
Characters and Groups!


### How to use it
Just subscribe to [NotifyMeSenpai](https://t.me/notifymesenpai_bot) and start playing around!

Use the following commands:
- **/add** - Follow the links you love :smirk:
- **/remove** - Unfollow the links you don't love anymore :confused:
- **/status** - Get a list of the links you're following :information_source:
- **/settings** - Change some personal parameters :wrench:


### Limitations
The amount of links that you can follow is limited. This choice was taken for two reasons:
1. To discourage abusive behaviors. People who love to see the world burn :fire: can `/add` a massive amount of links,
effectively clogging the bot and making it unusable/unstable.
2. To "equally" distribute compute power among users. No user has advantages over another


### Future features
Just a list of features I would like to implement:
- [x] Switch from SQLite3 to PostgreSQL. Will fix [#7](https://github.com/brodo97/NotifyMeSenpai/issues/7)
- [ ] Administration tools (Like /ban)
- [ ] Logger to keep track of what the logic is doing
- [ ] Tag/Character/Parody/Artist Leaderboard. What people follow the most
- [ ] Ideas... ?

### Current state of the project
The bot works well. All the things like the structure, classes and other files are a bit of a mess.
I'm still learning, but I'd like the project to be as much [PEP](https://peps.python.org/) compliant as possible



# DISCLAIMERS

### :underage: Notice to Minors :underage:
**This bot is not directed at and is not intended to be visited by minors.**
If you are a minor, do not use this bot.

### Links to Third-Party Websites
This bot will send you links to third-party websites or other content. I cannot control these third-party links or the
content found therein. I am not responsible for the content of any third-party website, and the inclusion of any links
to such third-party websites does not constitute or imply any recommendation, approval or endorsement of such
third-party websites.

### Technical information
When you use this bot, the server collect technical information such as the identification number of user's Telegram
accounts. The server collects this information to administer and manage the bot, to ensure that it functions properly
and to obtain and review bot-related statistics and information (for example, verifying system and server integrity).
The server do not collect any other personal information that can, in any way, lead the personal identification of the
user

# Contributing to this project
I'm seeking bug reports and feature requests.

# Other notes
[Handy fix](https://github.com/PostgresApp/PostgresApp/issues/313#issuecomment-192461641) for PostgreSQL's error:
`psql: FATAL: role "USER" does not exist`

# Donate
If this project helped you, you can buy me a beer or a cup of coffee! :wink:

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue.svg?style=for-the-badge&logo=paypal)](
https://www.paypal.me/notifysenpai)
