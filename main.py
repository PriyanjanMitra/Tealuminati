import discord
from discord.ext import commands, tasks
import requests
import xml.etree.ElementTree as ET
import asyncio
from datetime import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

DISCORD_TOKEN = "MTQ5MTEzNzM0Mjg4MTQwMzA1MQ.GkiR2m.tOVRZeWzyV8d4TdSx_NAcdB25Y_A1tT-M6SYYs"
REGION_NAME = "Britannia"
CHECK_INTERVAL = 10
NOTIFICATION_CHANNEL_ID = 1493815461349953616

HOME_OFFICE_ROLE_ID = 1493383252290048000
DEPUTY_PM_ROLE_ID = 1493384004064247909
PRIME_MINISTER_ROLE_ID = 1493383007808131102
CABINET_SECRETARY_ROLE_ID = 1493383060660420628

OLD_DATA_FILE = "known_nations_old.json"
NEW_DATA_FILE = "known_nations_new.json"
BACKUP_FILE = "known_nations_backup.json"

# GitHub configuration
GITHUB_REPO_URL = "https://github.com/PriyanjanMitra/Tealuminati.git"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # Set this in Replit secrets

class NationStatesMonitor(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.current_nations = set()
        self.previous_nations = set()
        self.check_count = 0
        self.git_configured = False

    def setup_git(self):
        if self.git_configured:
            return True
        
        try:
            if not os.path.exists(".git"):
                subprocess.run(['git', 'init'], capture_output=True, check=True)
                print("Git repository initialized")
            
            if GITHUB_TOKEN:
                auth_url = f"https://{GITHUB_TOKEN}@github.com/PriyanjanMitra/Tealuminati.git"
                subprocess.run(['git', 'remote', 'remove', 'origin'], capture_output=True)
                subprocess.run(['git', 'remote', 'add', 'origin', auth_url], capture_output=True, check=True)
                print("Git remote configured with token")
            else:
                subprocess.run(['git', 'remote', 'add', 'origin', GITHUB_REPO_URL], capture_output=True)
                print("Git remote configured (no token)")
            
            subprocess.run(['git', 'config', 'user.email', 'bot@tealuminati.com'], capture_output=True)
            subprocess.run(['git', 'config', 'user.name', 'Tealuminati Bot'], capture_output=True)
            
            try:
                subprocess.run(['git', 'pull', 'origin', 'main'], capture_output=True)
            except:
                try:
                    subprocess.run(['git', 'pull', 'origin', 'master'], capture_output=True)
                except:
                    pass
            
            self.git_configured = True
            return True
        except Exception as e:
            print(f"Git setup error: {e}")
            return False

    def git_push(self, filename, msg):
        if not self.setup_git():
            return False
        
        try:
            subprocess.run(['git', 'add', filename], capture_output=True, check=True)
            commit_result = subprocess.run(['git', 'commit', '-m', msg], capture_output=True)
            
            push_result = subprocess.run(['git', 'push', '-u', 'origin', 'main'], capture_output=True)
            if push_result.returncode != 0:
                push_result = subprocess.run(['git', 'push', '-u', 'origin', 'master'], capture_output=True)
            
            return push_result.returncode == 0
        except Exception as e:
            print(f"Git push error: {e}")
            return False

    def save_backup(self, nations, change_type=""):
        data = {
            'timestamp': datetime.now().isoformat(),
            'region': REGION_NAME,
            'nations_count': len(nations),
            'nations': sorted(list(nations)),
            'check_count': self.check_count
        }
        with open(BACKUP_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        success = self.git_push(BACKUP_FILE, f"Backup: {len(nations)} nations - {change_type}")
        if success:
            print(f"Backup pushed to GitHub: {len(nations)} nations")
        else:
            print("Failed to push to GitHub")

    def load_previous(self):
        if os.path.exists(OLD_DATA_FILE):
            with open(OLD_DATA_FILE, 'r') as f:
                return set(json.load(f).get('nations', []))
        return set()

    def save_current(self, nations, filename):
        data = {
            'timestamp': datetime.now().isoformat(),
            'region': REGION_NAME,
            'nations_count': len(nations),
            'nations': sorted(list(nations))
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    async def get_region_nations(self):
        try:
            url = f"https://www.nationstates.net/cgi-bin/api.cgi?region={REGION_NAME}&q=nations"
            headers = {'User-Agent': 'TealuminatiMonitorBot/1.0'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                nations_element = root.find('NATIONS')
                if nations_element is not None and nations_element.text:
                    nations_text = nations_element.text.strip()
                    if ',' in nations_text:
                        nations = set(n.strip() for n in nations_text.split(',') if n.strip())
                    elif ':' in nations_text:
                        nations = set(n.strip() for n in nations_text.split(':') if n.strip())
                    else:
                        nations = {nations_text}
                    return nations
            return None
        except Exception as e:
            print(f"API error: {e}")
            return None

    async def get_pings(self):
        channel = self.get_channel(NOTIFICATION_CHANNEL_ID)
        if not channel or not channel.guild:
            return ""
        
        guild = channel.guild
        pings = []
        for role_id in [HOME_OFFICE_ROLE_ID, DEPUTY_PM_ROLE_ID, PRIME_MINISTER_ROLE_ID, CABINET_SECRETARY_ROLE_ID]:
            role = guild.get_role(role_id)
            if role:
                pings.append(role.mention)
        return " ".join(pings)

    async def send_notification(self, nation_name, change_type):
        channel = self.get_channel(NOTIFICATION_CHANNEL_ID)
        if not channel:
            return
        
        nation_slug = nation_name.lower().replace(' ', '_')
        nation_url = f"https://www.nationstates.net/nation={nation_slug}"
        region_url = f"https://www.nationstates.net/region={REGION_NAME.lower().replace(' ', '_')}"
        
        if change_type == "added":
            embed = discord.Embed(title="NEW NATION JOINED", description=f"{nation_name} has entered the region!", color=discord.Color.green())
        else:
            embed = discord.Embed(title="NATION LEFT", description=f"{nation_name} has left the region!", color=discord.Color.red())
        
        embed.add_field(name="Nation", value=f"[Click to view]({nation_url})", inline=False)
        embed.add_field(name="Region", value=f"[Click to view]({region_url})", inline=True)
        embed.timestamp = datetime.now()
        
        try:
            if change_type == "added":
                pings = await self.get_pings()
                if pings:
                    await channel.send(pings)
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Notification error: {e}")

    async def process_updates(self):
        current = await self.get_region_nations()
        if not current:
            return
        
        self.save_current(current, NEW_DATA_FILE)
        previous = self.load_previous()
        
        if not previous:
            shutil.copy2(NEW_DATA_FILE, OLD_DATA_FILE)
            self.previous_nations = current
            self.current_nations = current
            self.save_backup(current, "initial")
            print(f"Initial setup complete: {len(current)} nations")
            return
        
        self.previous_nations = previous
        self.current_nations = current
        
        added = current - previous
        removed = previous - current
        
        if added or removed:
            for nation in added:
                await self.send_notification(nation, "added")
                await asyncio.sleep(1)
            for nation in removed:
                await self.send_notification(nation, "removed")
                await asyncio.sleep(1)
            
            shutil.copy2(NEW_DATA_FILE, OLD_DATA_FILE)
            self.save_backup(current, f"added_{len(added)}_removed_{len(removed)}")
            print(f"Changes detected: +{len(added)} -{len(removed)}")
        else:
            shutil.copy2(NEW_DATA_FILE, OLD_DATA_FILE)
            if self.check_count % 10 == 0:
                self.save_backup(current, "periodic")
        
        self.check_count += 1

    async def setup_hook(self):
        self.monitoring_task.start()

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def monitoring_task(self):
        await self.process_updates()

    @monitoring_task.before_loop
    async def before_monitoring(self):
        await self.wait_until_ready()
        print("Setting up Git...")
        self.setup_git()
        await asyncio.sleep(5)
        await self.process_updates()

bot = NationStatesMonitor()

@bot.command(name='status')
async def status(ctx):
    embed = discord.Embed(title="Bot Status", color=discord.Color.blue())
    embed.add_field(name="Region", value=REGION_NAME)
    embed.add_field(name="Checks", value=str(bot.check_count))
    embed.add_field(name="Current Nations", value=str(len(bot.current_nations)) if bot.current_nations else "0")
    embed.add_field(name="GitHub Backup", value="Configured" if bot.git_configured else "Not configured")
    await ctx.send(embed=embed)

@bot.command(name='forcecheck')
async def forcecheck(ctx):
    await ctx.send("Checking...")
    await bot.process_updates()
    await ctx.send("Done!")

@bot.command(name='backupnow')
@commands.has_permissions(administrator=True)
async def backupnow(ctx):
    """Manually push current backup to GitHub"""
    await ctx.send("Pushing backup to GitHub...")
    if bot.current_nations:
        bot.save_backup(bot.current_nations, "manual")
        await ctx.send("Backup pushed to GitHub!")
    else:
        await ctx.send("No data available")

@bot.command(name='setpingroles')
@commands.has_permissions(administrator=True)
async def setpingroles(ctx, home: discord.Role = None, deputy: discord.Role = None, pm: discord.Role = None, cabinet: discord.Role = None):
    global HOME_OFFICE_ROLE_ID, DEPUTY_PM_ROLE_ID, PRIME_MINISTER_ROLE_ID, CABINET_SECRETARY_ROLE_ID
    
    if home: HOME_OFFICE_ROLE_ID = home.id
    if deputy: DEPUTY_PM_ROLE_ID = deputy.id
    if pm: PRIME_MINISTER_ROLE_ID = pm.id
    if cabinet: CABINET_SECRETARY_ROLE_ID = cabinet.id
    
    config = {
        'home_office_role_id': HOME_OFFICE_ROLE_ID,
        'deputy_pm_role_id': DEPUTY_PM_ROLE_ID,
        'prime_minister_role_id': PRIME_MINISTER_ROLE_ID,
        'cabinet_secretary_role_id': CABINET_SECRETARY_ROLE_ID
    }
    with open('ping_roles_config.json', 'w') as f:
        json.dump(config, f)
    await ctx.send("Roles updated!")

@bot.event
async def on_ready():
    if os.path.exists('ping_roles_config.json'):
        with open('ping_roles_config.json', 'r') as f:
            config = json.load(f)
            global HOME_OFFICE_ROLE_ID, DEPUTY_PM_ROLE_ID, PRIME_MINISTER_ROLE_ID, CABINET_SECRETARY_ROLE_ID
            HOME_OFFICE_ROLE_ID = config.get('home_office_role_id', HOME_OFFICE_ROLE_ID)
            DEPUTY_PM_ROLE_ID = config.get('deputy_pm_role_id', DEPUTY_PM_ROLE_ID)
            PRIME_MINISTER_ROLE_ID = config.get('prime_minister_role_id', PRIME_MINISTER_ROLE_ID)
            CABINET_SECRETARY_ROLE_ID = config.get('cabinet_secretary_role_id', CABINET_SECRETARY_ROLE_ID)
    
    print(f"Bot ready: {bot.user}")
    print(f"GitHub repo: {GITHUB_REPO_URL}")
    await bot.change_presence(activity=discord.Game(name=f"Monitoring {REGION_NAME}"))

if __name__ == "__main__":
    from keep_alive import keep_alive
    keep_alive()
    bot.run(DISCORD_TOKEN)