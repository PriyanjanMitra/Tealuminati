import discord
from discord.ext import commands, tasks
import requests
import xml.etree.ElementTree as ET
import asyncio
from datetime import datetime
import json
import os
import shutil
from typing import Set, List
from keep_alive import keep_alive

# Configuration
DISCORD_TOKEN = "MTQ5MTEzNzM0Mjg4MTQwMzA1MQ.GkiR2m.tOVRZeWzyV8d4TdSx_NAcdB25Y_A1tT-M6SYYs"  # Replace with your bot token
REGION_NAME = "Britannia"  # Region to monitor
CHECK_INTERVAL = 10  # Check every 60 seconds
NOTIFICATION_CHANNEL_ID = 1493815461349953616  # Your channel ID

# File paths
OLD_DATA_FILE = "known_nations_old.json"
NEW_DATA_FILE = "known_nations_new.json"
BACKUP_FILE = "known_nations_backup.json"

keep_alive()
class NationStatesMonitor(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

        self.current_nations = set()
        self.previous_nations = set()
        self.notification_channel_id = NOTIFICATION_CHANNEL_ID
        self.check_count = 0

    def load_previous_nations(self) -> Set[str]:
        """Load the previous nations from the old JSON file"""
        if os.path.exists(OLD_DATA_FILE):
            try:
                with open(OLD_DATA_FILE, 'r') as f:
                    data = json.load(f)
                    nations = set(data.get('nations', []))
                    timestamp = data.get('timestamp', 'Unknown')
                    print(f"📁 Loaded previous nations: {len(nations)} nations from {timestamp}")
                    return nations
            except Exception as e:
                print(f"❌ Error loading old data: {e}")
        else:
            print("📁 No previous data file found. This is the first run.")
        return set()

    def save_nations_to_file(self, nations: Set[str], filename: str, description: str = ""):
        """Save nations to a JSON file with timestamp"""
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'region': REGION_NAME,
                'nations_count': len(nations),
                'nations': sorted(list(nations)),
                'description': description
            }
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"💾 Saved {len(nations)} nations to {filename}")
            return True
        except Exception as e:
            print(f"❌ Error saving to {filename}: {e}")
            return False

    def backup_current_data(self):
        """Create a backup of the current old data file"""
        if os.path.exists(OLD_DATA_FILE):
            try:
                shutil.copy2(OLD_DATA_FILE, BACKUP_FILE)
                print(f"📦 Created backup at {BACKUP_FILE}")
            except Exception as e:
                print(f"⚠️ Could not create backup: {e}")

    async def get_region_nations(self) -> Set[str]:
        """Fetch current nations from NationStates API and split by commas AND colons"""
        try:
            url = f"https://www.nationstates.net/cgi-bin/api.cgi?region={REGION_NAME}&q=nations"
            headers = {'User-Agent': 'BritanniaMonitorBot/1.0 (Contact: your@email.com)'}

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                root = ET.fromstring(response.content)
                nations_element = root.find('NATIONS')

                if nations_element is not None and nations_element.text:
                    nations_text = nations_element.text.strip()
                    if nations_text:
                        # Split by commas first (standard API format)
                        if ',' in nations_text:
                            nations_list = [n.strip() for n in nations_text.split(',') if n.strip()]
                        # If no commas but has colons, split by colons
                        elif ':' in nations_text:
                            nations_list = [n.strip() for n in nations_text.split(':') if n.strip()]
                        else:
                            nations_list = [nations_text]

                        nations = set(nations_list)
                        print(f"🌐 API returned {len(nations)} nations from {REGION_NAME}")
                        if len(nations) <= 20:
                            print(f"   Nations: {', '.join(nations)}")
                        else:
                            print(f"   First 20: {', '.join(list(nations)[:20])}")
                        return nations
                print(f"⚠️ No nations found in API response")
                return set()
            else:
                print(f"❌ API Error: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ API Exception: {e}")
            return None

    def compare_nations(self, old: Set[str], new: Set[str]) -> tuple:
        """Compare two sets of nations and return additions and removals"""
        added = new - old
        removed = old - new
        return added, removed

    async def send_notification(self, nation_name: str, change_type: str):
        """Send Discord notification for nation changes"""
        channel = self.get_channel(self.notification_channel_id)

        if not channel:
            print(f"❌ Channel {self.notification_channel_id} not found!")
            return

        # Clean the nation name for URL (remove special characters)
        nation_slug = nation_name.lower().replace(' ', '_').replace(':', '_').replace('-', '_')
        nation_url = f"https://www.nationstates.net/nation={nation_slug}"
        region_url = f"https://www.nationstates.net/region={REGION_NAME.lower().replace(' ', '_')}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        if change_type == "added":
            embed = discord.Embed(
                title="🏰 NEW NATION JOINED BRITANNIA!",
                description=f"**{nation_name}** has entered the region!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
        else:
            embed = discord.Embed(
                title="📤 NATION LEFT BRITANNIA",
                description=f"**{nation_name}** has left the region!",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )

        embed.add_field(name="📖 Nation", value=f"[Click to view]({nation_url})", inline=False)
        embed.add_field(name="🌍 Region", value=f"[Click to view]({region_url})", inline=True)
        embed.add_field(name="🕐 Time", value=timestamp, inline=True)
        embed.set_footer(text=f"Monitoring {REGION_NAME}")

        # Send notification
        try:
            await channel.send(embed=embed)
            print(f"   ✅ {change_type.upper()} notification sent for {nation_name}")
            return True
        except Exception as e:
            print(f"   ❌ Failed to send embed: {e}")
            # Fallback to plain text (shortened if needed)
            try:
                emoji = "➕" if change_type == "added" else "➖"
                # Truncate nation name if too long
                display_name = nation_name[:100] + "..." if len(nation_name) > 100 else nation_name
                message = f"{emoji} **{change_type.upper()}** {display_name} {'joined' if change_type == 'added' else 'left'} {REGION_NAME}!\n{nation_url}"
                await channel.send(message)
                print(f"   ✅ Text fallback sent for {nation_name}")
                return True
            except Exception as e2:
                print(f"   ❌ Even text fallback failed: {e2}")
                return False

    async def process_updates(self):
        """Main function to check for updates using the two-file system"""
        print(f"\n{'=' * 60}")
        print(f"🔍 UPDATE CHECK #{self.check_count + 1} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}")

        # Step 1: Get current nations from API
        print("📡 Fetching current nations from NationStates API...")
        current_nations = await self.get_region_nations()

        if current_nations is None:
            print("❌ Could not fetch data from API. Skipping this check.")
            return

        if not current_nations:
            print("⚠️ API returned empty set. This might be an error. Skipping update.")
            return

        # Step 2: Save current nations to NEW file
        print(f"💾 Saving current nations to {NEW_DATA_FILE}...")
        self.save_nations_to_file(current_nations, NEW_DATA_FILE, "Current region data")

        # Step 3: Load previous nations from OLD file
        print(f"📂 Loading previous nations from {OLD_DATA_FILE}...")
        previous_nations = self.load_previous_nations()

        # Step 4: If no previous data exists, this is first run
        if not previous_nations:
            print("🎯 First run detected! Setting baseline...")
            shutil.copy2(NEW_DATA_FILE, OLD_DATA_FILE)
            self.previous_nations = current_nations
            self.current_nations = current_nations
            print(f"✅ Baseline established with {len(current_nations)} nations")

            # Send startup message to Discord
            channel = self.get_channel(self.notification_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🟢 Bot Online - Monitoring Started",
                    description=f"Now monitoring **{REGION_NAME}** region!",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="📊 Initial Nations", value=str(len(current_nations)), inline=True)
                embed.add_field(name="⏱️ Check Interval", value=f"{CHECK_INTERVAL} seconds", inline=True)
                await channel.send(embed=embed)
            return

        # Step 5: Compare old vs new
        self.previous_nations = previous_nations
        self.current_nations = current_nations

        added_nations, removed_nations = self.compare_nations(previous_nations, current_nations)

        # Step 6: Display comparison results
        print(f"\n📊 COMPARISON RESULTS:")
        print(f"   Previous nations: {len(previous_nations)}")
        print(f"   Current nations:  {len(current_nations)}")
        print(f"   Added: {len(added_nations)}")
        print(f"   Removed: {len(removed_nations)}")

        if added_nations:
            print(f"\n✨ NATIONS ADDED:")
            for nation in sorted(added_nations)[:20]:  # Show first 20
                print(f"   ➕ {nation}")
            if len(added_nations) > 20:
                print(f"   ... and {len(added_nations) - 20} more")

        if removed_nations:
            print(f"\n📤 NATIONS REMOVED:")
            for nation in sorted(removed_nations)[:20]:
                print(f"   ➖ {nation}")
            if len(removed_nations) > 20:
                print(f"   ... and {len(removed_nations) - 20} more")

        # Step 7: Send notifications for changes
        if added_nations or removed_nations:
            print(f"\n📨 Sending Discord notifications...")

            # Send notifications for new nations
            for nation in sorted(added_nations):
                await self.send_notification(nation, "added")
                await asyncio.sleep(1)  # Delay between notifications

            # Send notifications for nations that left
            for nation in sorted(removed_nations):
                await self.send_notification(nation, "removed")
                await asyncio.sleep(1)

            # Step 8: Create backup before overwriting
            print(f"\n📦 Creating backup of old data...")
            self.backup_current_data()

            # Step 9: Overwrite OLD file with NEW file
            print(f"🔄 Updating {OLD_DATA_FILE} with current data...")
            shutil.copy2(NEW_DATA_FILE, OLD_DATA_FILE)
            print(f"✅ Update complete! Old file replaced with current data.")

        else:
            print(f"\n📭 No changes detected in this update cycle.")
            # Still update the OLD file to keep timestamps current
            shutil.copy2(NEW_DATA_FILE, OLD_DATA_FILE)
            print(f"🔄 Updated timestamp in {OLD_DATA_FILE} (no content changes)")

        self.check_count += 1
        print(f"\n✅ Update check #{self.check_count} completed!")

    async def setup_hook(self):
        """Setup background task"""
        self.monitoring_task.start()

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def monitoring_task(self):
        """Background monitoring task"""
        await self.process_updates()

    @monitoring_task.before_loop
    async def before_monitoring(self):
        """Wait for bot to be ready"""
        await self.wait_until_ready()
        print("✅ Bot is ready! Starting monitoring system...")
        await asyncio.sleep(5)
        print("🚀 Initiating first region check...")
        await self.process_updates()


# Create bot instance
bot = NationStatesMonitor()


# ============= DISCORD COMMANDS =============

@bot.command(name='status')
async def status_command(ctx):
    """Show bot status and comparison info"""
    embed = discord.Embed(
        title="🤖 NationStates Monitor Status",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="📍 Region", value=REGION_NAME, inline=True)
    embed.add_field(name="⏱️ Check Interval", value=f"{CHECK_INTERVAL}s", inline=True)
    embed.add_field(name="📊 Checks Performed", value=str(bot.check_count), inline=True)
    embed.add_field(name="📁 Old Data File", value="✅ Exists" if os.path.exists(OLD_DATA_FILE) else "❌ Missing",
                    inline=True)
    embed.add_field(name="📁 New Data File", value="✅ Exists" if os.path.exists(NEW_DATA_FILE) else "❌ Missing",
                    inline=True)

    if bot.current_nations:
        embed.add_field(name="🔄 Current Nations", value=str(len(bot.current_nations)), inline=True)
        if bot.current_nations:
            preview = ", ".join(list(bot.current_nations)[:5])
            embed.add_field(name="Sample Nations", value=preview, inline=False)

    await ctx.send(embed=embed)


@bot.command(name='compare')
async def compare_command(ctx):
    """Manually compare old and new files and show differences"""
    await ctx.send("🔍 Comparing old and new nation lists...")

    old_nations = set()
    new_nations = set()

    if os.path.exists(OLD_DATA_FILE):
        with open(OLD_DATA_FILE, 'r') as f:
            data = json.load(f)
            old_nations = set(data.get('nations', []))

    if os.path.exists(NEW_DATA_FILE):
        with open(NEW_DATA_FILE, 'r') as f:
            data = json.load(f)
            new_nations = set(data.get('nations', []))

    if not old_nations and not new_nations:
        await ctx.send("❌ No data files found. Run the bot first to generate them.")
        return

    added = new_nations - old_nations
    removed = old_nations - new_nations

    embed = discord.Embed(
        title="📊 Comparison Results",
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Old Nations", value=str(len(old_nations)), inline=True)
    embed.add_field(name="New Nations", value=str(len(new_nations)), inline=True)
    embed.add_field(name="Added", value=str(len(added)), inline=True)
    embed.add_field(name="Removed", value=str(len(removed)), inline=True)

    if added:
        added_text = "\n".join(f"➕ {n}" for n in sorted(added)[:20])
        if len(added) > 20:
            added_text += f"\n... and {len(added) - 20} more"
        embed.add_field(name="✨ Added Nations", value=added_text, inline=False)

    if removed:
        removed_text = "\n".join(f"➖ {n}" for n in sorted(removed)[:20])
        if len(removed) > 20:
            removed_text += f"\n... and {len(removed) - 20} more"
        embed.add_field(name="📤 Removed Nations", value=removed_text, inline=False)

    await ctx.send(embed=embed)


@bot.command(name='test')
async def test_command(ctx):
    """Send a test notification"""
    await ctx.send("🧪 Sending test notification...")
    await bot.send_notification("TestNation", "added")
    await ctx.send("✅ Test notification sent!")


@bot.command(name='forcecheck')
async def force_check_command(ctx):
    """Force an immediate region check"""
    await ctx.send("🔄 Forcing immediate region check...")
    await bot.process_updates()
    await ctx.send("✅ Check completed!")


@bot.command(name='reset')
@commands.has_permissions(administrator=True)
async def reset_command(ctx):
    """Reset all data files (admin only)"""
    await ctx.send("⚠️ Resetting all data files...")

    for file in [OLD_DATA_FILE, NEW_DATA_FILE, BACKUP_FILE]:
        if os.path.exists(file):
            os.remove(file)

    bot.current_nations = set()
    bot.previous_nations = set()
    bot.check_count = 0

    await ctx.send("✅ Reset complete! Bot will rebuild data on next check.")
    await force_check_command(ctx)


@bot.event
async def on_ready():
    print(f"\n{'=' * 60}")
    print(f"✅ Bot Connected: {bot.user} (ID: {bot.user.id})")
    print(f"📍 Monitoring Region: {REGION_NAME}")
    print(f"⏱️ Check Interval: {CHECK_INTERVAL} seconds")
    print(f"📢 Notification Channel: {bot.notification_channel_id}")
    print(f"{'=' * 60}\n")

    # Send startup message
    channel = bot.get_channel(bot.notification_channel_id)
    if channel:
        embed = discord.Embed(
            title="🟢 Bot Online",
            description=f"Monitoring **{REGION_NAME}** region!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await channel.send(embed=embed)
        print("✅ Startup message sent to Discord")

    # Set status
    await bot.change_presence(activity=discord.Game(name=f"Monitoring {REGION_NAME}"))


# Run the bot
if __name__ == "__main__":
    print("🚀 Starting NationStates Monitor Bot...")

    if DISCORD_TOKEN == "YOUR_DISCORD_BOT_TOKEN":
        print("❌ ERROR: Please set your DISCORD_TOKEN in the script!")
        exit(1)

    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()