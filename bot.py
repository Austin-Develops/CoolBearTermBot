from discord.ext.commands.bot import Bot
from discord.app_commands import checks, check
import discord
from Secret import token
import json
import os
import traceback
import subprocess
import sys
from pathlib import Path
from Levenshtein import distance
import datetime

def dprint(*args, **kwargs):
    print(f'[Cool Bear] {str(datetime.datetime.now())}:', *args, **kwargs)

intents = discord.Intents.default()
intents.message_content = True

myBot = Bot('!', intents=intents)

dprint(sys.argv)
online_message_channel = None if len(sys.argv) <= 1 else int(sys.argv[1])

'''
format
{
    operator_role_id: operator_role_id
    term_role_id: term_role_id,
    data: {
        "term": {
            'Aliases': [
                'Alias1',
                'Alias2'
            ],
            'Message': 'This message defines the term',
            'Files': [
                'filename1',
                'filename2',
                'filename3'
            ]
        }
    }
}
'''

DATA_FILE_PATH = 'data.json'

class Config:
    def __init__(self):
        self.load_data()
        self.BOT_DEV_ID = None
        self.initially_spoken = False

    def load_data(self):
        if os.path.exists(DATA_FILE_PATH):
            with open(DATA_FILE_PATH, 'r') as file:
                json_data: dict = json.load(file)
                self.data = json_data.get('data', {})
                self.operator_role_id = json_data.get('operator_role_id', None)
                self.term_role_id = json_data.get('term_role_id', None)
        else:
            self.data = {}
            self.operator_role_id = None
            self.term_role_id = None

    def save_data(self):
        with open(DATA_FILE_PATH, 'w') as file:
            save_data = {
                'operator_role_id': self.operator_role_id,
                'term_role_id': self.term_role_id,
                'data': self.data
            }
            json.dump(save_data, file, indent=4)
    
    async def get_info(self):
        info = await myBot.application_info()
        self.BOT_DEV_ID = info.owner.id


config = Config()

async def guild_only(ctx):
    return ctx.guild is not None

async def is_owner(ctx):
    return ctx.user.id == config.BOT_DEV_ID

async def is_operator(ctx: discord.Interaction):
    return ctx.user.id == config.BOT_DEV_ID or isinstance(ctx.user, discord.Member) and config.operator_role_id in [r.id for r in ctx.user.roles]

async def is_termer(ctx: discord.Interaction):
    return ctx.user.id == config.BOT_DEV_ID or isinstance(ctx.user, discord.Member) and config.term_role_id in [r.id for r in ctx.user.roles]

@myBot.event
async def setup_hook():
    await config.get_info()


def spellcheck(term):

    lowest_num = float('inf')
    lowest_terms = []
    for key, value_dict in config.data.items():
        dist = distance(term, key)
        if dist == 0:
            return 0, [key]
        elif dist < lowest_num:
            lowest_num = dist
            lowest_terms = [key]
        elif dist == lowest_num:
            lowest_terms.append(key)
        
        for thing in value_dict['Aliases']:
            dist = distance(term, thing)
            if dist == 0:
                return 0, [key]
            elif dist < lowest_num:
                lowest_num = dist
                lowest_terms = [thing]
            elif dist == lowest_num:
                lowest_terms.append(thing)
    
    return lowest_num, [] if lowest_num > 3 else lowest_terms
        

def join_list(word_list):
    word_list_len = len(word_list)
    assert word_list_len >= 1

    if word_list_len == 1:
        return '`' + word_list[0] + '`'
    elif word_list_len == 2:
        return f'`{word_list[0]}` or `{word_list[1]}`'
    elif word_list_len >= 3:
        return '`' + '`, `'.join(word_list[:-1]) + '`, or `' + word_list[-1] + '`'


@myBot.event
async def on_message(message: discord.Message):
    if message.author.id == myBot.user.id:
        return
    
    if message.content == '!sync' and message.author.id == config.BOT_DEV_ID:
        dprint(myBot.guilds)
        # myBot.tree.add_command(set_primary_server, guild=myBot.guilds[0])
        await myBot.tree.sync()
        await message.channel.send('Synced!')
        return

@myBot.event
async def on_ready():
    dprint(online_message_channel, config.initially_spoken)
    if online_message_channel is not None and not config.initially_spoken:
        config.initially_spoken = True
        target_channel = myBot.get_channel(online_message_channel)
        dprint(target_channel, ':)')
        if target_channel is not None:
            await target_channel.send('Restarted (Dev Branch)!')
            await myBot.tree.sync()

@myBot.tree.command(name='set_config_file', description='Sets data file')
@check(guild_only)
@check(is_operator)
async def set_config_file(ctx: discord.Interaction, file: discord.Attachment):
    if not file.filename.endswith('.json'):
        await ctx.response.send_message('This is not a json file', ephemeral=True)
    
    text = (await file.read()).decode()
    with open('old data.json', 'w') as newfile:
        json.dump(config.data, newfile, indent=4)
    
    with open('data.json', 'w') as newfile:
        newfile.write(text)
    
    config.load_data()
    await ctx.response.send_message('config updated!')


@myBot.tree.command(name='get_config_file', description='Sets data file')
@check(guild_only)
@check(is_operator)
async def get_config_file(ctx: discord.Interaction):
    newfile = discord.File('data.json')
    await ctx.response.send_message(file=newfile, ephemeral=True)


@myBot.tree.command(name='set_operator', description='Sets operator role')
@check(guild_only)
@check(is_operator)
async def set_operator_role(ctx: discord.Interaction, role: discord.Role):
    config.operator_role_id = role.id
    config.save_data()
    await ctx.response.send_message('Updated!')


@myBot.tree.command(name='set_termer', description='Sets termer role')
@check(guild_only)
@check(is_operator)
async def set_termer_role(ctx: discord.Interaction, role: discord.Role):
    config.term_role_id = role.id
    config.save_data()
    await ctx.response.send_message('Updated!')


@myBot.tree.command(name='add_term', description='Adds a term')
@check(guild_only)
@check(is_termer)
async def add_term(ctx: discord.Interaction, term: str, definition: str | None = None,
                     file1: discord.Attachment | None = None, file2: discord.Attachment | None = None,
                     file3: discord.Attachment | None = None, file4: discord.Attachment | None = None):
    
    term = term.casefold()
    if term in config.data.keys():
        await ctx.response.send_message(f'*{term}* already exists inside of the dictionary')
        return
    
    await ctx.response.defer()

    files = [file for file in (file1, file2, file3, file4) if file is not None]
    true_files = []
    text = ''
    for file in files:
        try:
            existing_assets = os.listdir('assets')
            base, ext = os.path.splitext(file.filename)
            name = file.filename
            number = 0
            while name in existing_assets:
                number += 1
                name = f'{base} ({number}){ext}'

            bytes = await file.read()
            with open(os.path.join('assets', name), 'wb') as new_file:
                new_file.write(bytes)
            
            true_files.append(name)
            
        except discord.Forbidden:
            text += f'Failed to download `{file.filename}`. I do not have permissions to. Give me permissions and use /amend_term to add this file.\n'
        except discord.NotFound:
            text += f'Failed to download `{file.filename}`. This attachment was deleted. Use /amend_term to include this file.\n'
        except discord.HTTPException:
            text += f'Failed to download `{file.filename}`. Use /amend_term to try again.\n'

    if text:
        await ctx.followup.send(text)

    new_item = {
        'Aliases': [],
        'Message': '' if definition is None else definition,
        'Files': true_files
    }

    config.data[term] = new_item
    config.save_data()
    await ctx.followup.send(f'{term} has been added!')


@myBot.tree.command(name='alias', description='View or set aliases for a term (\'|\' separated)')
@check(guild_only)
@check(is_termer)
async def alias(ctx: discord.Interaction, term: str, aliases: str | None = None):
    await ctx.response.defer()
    term = term.casefold()
    diff_level, closest_words = spellcheck(term)

    if diff_level != 0:
        if not closest_words:
            await ctx.followup.send(f'`{term}` could not be found as a term.')
        else:
            await ctx.followup.send(f'`{term}` could not be found as a term. Did you mean ' + join_list(closest_words) + '?')
        return

    if aliases is None:
        term = closest_words[0]
        aliases_found = config.data[term]['Aliases']
        embed = discord.Embed()
        embed.title = 'Aliases for ' + term
        if aliases_found:
            embed.description = '`' + '`, `'.join(aliases_found) + '`'
        else:
            embed.description = 'No aliases provided.'
        embed.color = discord.Color.teal()
        await ctx.followup.send(embed=embed)
        return
    else:
        aliases = aliases.casefold()
        splits = [alias.strip() for alias in aliases.split('|')]
        config.data[term]['Aliases'] = splits
        config.save_data()
        await ctx.followup.send(f'The aliases for `{term}` have been updated!')
        return


@myBot.tree.command(name='amend_term', description='Updates a term')
@check(guild_only)
@check(is_termer)
async def amend_term(ctx: discord.Interaction, term: str, definition: str | None = None,
                     file1: discord.Attachment | None = None, file2: discord.Attachment | None = None,
                     file3: discord.Attachment | None = None, file4: discord.Attachment | None = None):
    # TODO
    term = term.casefold()
    diff_level, closest_words = spellcheck(term)

    if diff_level != 0:
        if not closest_words:
            await ctx.response.send_message(f'`{term}` could not be found as a term.')
        else:
            await ctx.response.send_message(f'`{term}` could not be found as a term. Did you mean ' + join_list(closest_words) + '?')
        return
    
    await ctx.response.defer()

    files = [file for file in (file1, file2, file3, file4) if file is not None]
    true_files = []
    text = ''
    for file in files:
        try:
            existing_assets = os.listdir('assets')
            base, ext = os.path.splitext(file.filename)
            name = file.filename
            number = 0
            while name in existing_assets:
                number += 1
                name = f'{base} ({number}){ext}'

            bytes = await file.read()
            with open(os.path.join('assets', name), 'wb') as new_file:
                new_file.write(bytes)
            
            true_files.append(name)
            
        except discord.Forbidden:
            text += f'Failed to download `{file.filename}`. I do not have permissions to. Give me permissions and use /amend_term to add this file.\n'
        except discord.NotFound:
            text += f'Failed to download `{file.filename}`. This attachment was deleted. Use /amend_term to include this file.\n'
        except discord.HTTPException:
            text += f'Failed to download `{file.filename}`. Use /amend_term to try again.\n'

    if text:
        await ctx.followup.send(text)

    new_item = {
        'Aliases': [],
        'Message': '' if definition is None else definition,
        'Files': true_files
    }

    config.data[term] = new_item
    config.save_data()
    await ctx.followup.send(f'`{term}` has been updated!')


@myBot.tree.command(name='delete_term', description='Removes a term')
@check(guild_only)
@check(is_termer)
async def del_term(ctx: discord.Interaction, term: str):
    await ctx.response.defer()
    term = term.casefold()
    diff_level, closest_words = spellcheck(term)

    if diff_level != 0:
        if not closest_words:
            await ctx.followup.send(f'`{term}` could not be found as a term.')
        else:
            await ctx.followup.send(f'`{term}` could not be found as a term. Did you mean ' + join_list(closest_words) + '?')
        return
    
    else:
        term = closest_words[0]
        del config.data[term]
        config.save_data()
        await ctx.followup.send(f'`{term}` has been deleted!')


@myBot.tree.command(name='define', description='gets the definition of a term')
@check(guild_only)
async def define(ctx: discord.Interaction, term: str):
    await ctx.response.defer()
    term = term.casefold()
    diff_level, closest_words = spellcheck(term)

    if diff_level != 0:
        if not closest_words:
            await ctx.followup.send(f'`{term}` could not be found as a term.')
        else:
            await ctx.followup.send(f'`{term}` could not be found as a term. Did you mean ' + join_list(closest_words) + '?')
        return
    
    else:
        term = closest_words[0]
        term_data = config.data[term]
        embed = discord.Embed()
        embed.title = f'/define {term}'
        embed.description = f'''Aliases: {'{None}' if not term_data['Aliases'] else ', '.join(term_data['Aliases'])}

{term_data['Message']}'''
        embed.colour = discord.Colour.teal()

        files = [discord.File(os.path.join('assets', filepath)) for filepath in config.data[term]['Files']]
        await ctx.followup.send(embed=embed)
        if files:
            new_msg = await ctx.channel.send('Uploading video...')
            await new_msg.edit(content=None, attachments=files)



@myBot.tree.command(name='terms', description='gets the definition of a term')
@check(guild_only)
async def get_term_list(ctx: discord.Interaction):
    embed = discord.Embed()
    embed.title = 'Term List'
    terms = sorted(config.data.keys())
    value = '(No terms defined)' if not terms else '`' + '`, `'.join(terms) + '`'
    embed.add_field(name='All terms', value=value, inline=False)
    embed.colour = discord.Colour.blue()
    await ctx.response.send_message(embed=embed)


# @myBot.tree.command(name='re_init', description='Gets everything from past isabelle bot messages')
# @check(guild_only)
# @check(is_owner)
# async def re_init(ctx: discord.Interaction):
#     await ctx.response.defer(thinking=True)
#     isabot_id = 513515391155175424
#     bot_channel = ctx.guild.get_channel(456667208139931649)
#     to_find = {'[dthrow] (delayed fair)', 'backdash cheerless', 'belay', 'belay desync', 'blizz', 'blizz confirms', 'blizzard wavedash', 'blizzblock', 'blizzwall', 'button storage desyncs', 'ccj fsmash', 'chars doc', 'cheer cancel', 'cheerless', 'dash dance buffer desync', 'desync', 'dtac', 'dthrow footstool', 'fair footstool', 'footstool squall', 'gimfinite', 'ib', 'ics megaguide', 'izaw guide', 'jab interrupt', 'landing lag desync', 'landing tilt desync', 'murasat combo', 'nair interrupt', 'nanapult', 'nanatrump', 'notation', 'nut', 'reconnect buffer', 'rollback desync', 'run state storage', 'run turn desync', 'ruri combo', 'semisync', 'shield jump storage', 'shieldstun desync', 'soymilk', 'soymilk gif guide', 'squall', 'squall desync', 'synced', 'teeter cheerless', 'throw desync', 'tilt turn', 'turn buffer desync', 'utilt footstool'}
#     terms = set()
#     async for message in bot_channel.history(limit=5000):
#         if message.author.id == isabot_id:
#             dprint(message.interaction_metadata)
    
#     await ctx.followup.send('Done')

#     ts doesn't work because the API doesn't include slash command data bruh. Has to be done manually


@myBot.tree.command(name='update', description='Restarts the bot (removing the message storage) to the current branch')
@check(guild_only)
@check(is_owner)
async def restart_and_update(ctx: discord.Interaction, branch: str | None = None):
    await ctx.response.defer(thinking=True)
    if branch is None:
        branch = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
        dprint(branch)
    
    # Define paths
    venv_win = Path(".venv/Scripts/python.exe")
    venv_unix = Path(".venv/bin/python")

    # Choose the correct Python path
    if venv_win.exists():
        venv_python = str(venv_win)
    elif venv_unix.exists():
        venv_python = str(venv_unix)
    else:
        await ctx.followup.send("Could not find virtual environment Python interpreter. Check manually.")
        return
    
    try:
        subprocess.run(['git', 'fetch', '--all'], check=True)
        subprocess.run(['git', 'switch', branch], check=True)
        subprocess.run(['git', 'pull', 'origin', branch], check=True)
        await ctx.followup.send('Restarting o7')
        subprocess.Popen([venv_python, 'bot.py', str(ctx.channel_id)])
    except Exception as e:
        await ctx.followup.send(traceback.format_exc(), ephemeral=True)
        await ctx.followup.send(f'Branch `{branch}` does not exist', ephemeral=True)
        return
    sys.exit(0)


@myBot.tree.command(name='kill', description='Turns off the bot. Kills the process')
@check(guild_only)
@check(is_owner)
async def kill_bot(ctx: discord.Interaction):
    await ctx.response.send_message('Powering off! o7')
    sys.exit(0)
                
myBot.run(token)