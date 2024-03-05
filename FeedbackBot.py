#!/usr/bin/env python3

import os

try:
    import discord
    from discord import app_commands
    from discord.ext import commands
    from discord.ext.commands import Paginator

    from dotenv import load_dotenv
    import sqlite3
except ImportError:
    import sys
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "discord.py", "python-dotenv", "sqlite3"])

    import discord
    from discord import app_commands
    from discord.ext import commands
    from discord.ext.commands import Paginator

    from dotenv import load_dotenv
    import sqlite3

load_dotenv()
bot = discord.Client(intents = discord.Intents.all())
tree = app_commands.CommandTree(bot)

conn = sqlite3.connect("feedback.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS feedback (investor TEXT, startup TEXT, feedback TEXT, rating INTEGER)")
conn.commit()
synced = False


@bot.event
async def on_ready():
    global synced

    print("Syncing commands... ", end = "")
    await bot.wait_until_ready()
    if not synced:
        await tree.sync()
        synced = True

    print("Done.")
    print(f"Logged in as {bot.user}.")
    print(f"Connected to {len(bot.guilds)} server(s).")


@bot.event
async def on_command_error(ctx: discord.Interaction, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.response.send_message("Missing required argument.")
    elif isinstance(error, commands.MissingRole):
        await ctx.response.send_message("You do not have permission to use this command.")
    else:
        print(error)


class Page(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(label = "⭐", custom_id = "star"))

    @discord.ui.button(label = "⭐", custom_id = "star")
    async def star_button(self, *_):
        self.stop()


class RatingDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label = str(i), value = str(i)) for i in range(1, 6)
        ]
        super().__init__(placeholder = "Select Rating", options = options, custom_id = "rating")


async def get_existing_feedback(ctx: discord.Interaction, investor: str):
    startup = ctx.user.name

    dropdown_view = discord.ui.View()
    dropdown_view.add_item(RatingDropdown())

    await ctx.response.send_message("Select a rating:", view = dropdown_view)
    interaction = await bot.wait_for("select_option", check = lambda i: i.user == ctx.user)
    c.execute("SELECT * FROM feedback WHERE investor=? AND startup=?", (investor, startup))

    return c.fetchone(), startup, int(interaction.values[0])


@tree.command(name = "submitfeedback", description = "Submit feedback for an investor with a rating.")
async def submit_feedback(ctx: discord.Interaction, investor: str, feedback: str):
    existing_feedback, startup, rating = await get_existing_feedback(ctx, investor)

    if existing_feedback:
        await ctx.response.send_message(
            f"Feedback for {investor} from {startup} already exists. Use `/updatefeedback` to modify.")
    else:
        c.execute("INSERT INTO feedback VALUES (?, ?, ?, ?)", (investor, startup, feedback, rating))
        conn.commit()
        await ctx.response.send_message(
            f"Feedback submitted for {investor} from {startup} with a rating of {rating} stars.")


@tree.command(name = "listinvestors", description = "List all investors with feedback.")
async def list_investors(ctx):
    c.execute("SELECT DISTINCT investor FROM feedback")
    investors = c.fetchall()

    msg = discord.Embed(color = 0x00ff00)
    msg.add_field(name = "Investors", value = "\n".join([investor[0] for investor in investors]), inline = False)
    await ctx.response.send_message(embed = msg)


@tree.command(name = "liststartups", description = "List all startups with feedback.")
async def list_startups(ctx):
    c.execute("SELECT DISTINCT startup FROM feedback")
    startups = c.fetchall()

    msg = discord.Embed(color = 0x00ff00)
    msg.add_field(name = "Startups", value = "\n".join([startup[0] for startup in startups]), inline = False)
    await ctx.response.send_message(embed = msg)


@tree.command(name = "deletefeedback", description = "Delete feedback for an investor.")
@commands.has_role("admin")
async def delete_feedback(ctx: discord.Interaction, investor: str):
    c.execute("SELECT * FROM feedback WHERE investor=?", (investor,))
    existing_feedback = c.fetchone()

    if existing_feedback:
        c.execute("DELETE FROM feedback WHERE investor=?", (investor,))
        conn.commit()

        await ctx.response.send_message(f"Feedback for {investor} deleted.")
    else:
        await ctx.response.send_message(f"No existing feedback found for {investor}.")


@tree.command(name = "startupfeedback", description = "List all feedback given by a startup.")
async def startup_feedback(ctx: discord.Interaction, startup: str):
    c.execute("SELECT investor, feedback, rating FROM feedback WHERE startup=?", (startup,))
    results = c.fetchall()

    if results:
        paginator = Paginator(prefix = "", suffix = "")
        for investor, feedback, rating in results:
            paginator.add_line(f"Investor: {investor}\nFeedback: {feedback}\nRating: {rating} stars\n")

        for page in paginator.pages:
            await ctx.response.send_message(page, view = Page())
    else:
        await ctx.response.send_message(f"No feedback found for {startup}.")


@tree.command(name = "investorfeedback", description = "List all feedback for an investor.")
async def investor_feedback(ctx: discord.Interaction, investor: str):
    c.execute("SELECT startup, feedback, rating FROM feedback WHERE investor=?", (investor,))
    results = c.fetchall()

    if results:
        paginator = Paginator(prefix = "", suffix = "")
        for startup, feedback, rating in results:
            paginator.add_line(f"Startup: {startup}\nFeedback: {feedback}\nRating: {rating} stars\n")

        for page in paginator.pages:
            await ctx.response.send_message(page, view = Page())
    else:
        await ctx.response.send_message(f"No feedback found for {investor}.")


@tree.command(name = "updatefeedback", description = "Update feedback for an investor.")
async def update_feedback(ctx: discord.Interaction, investor: str, feedback: str):
    existing_feedback, startup, rating = await get_existing_feedback(ctx, investor)

    if existing_feedback:
        c.execute("UPDATE feedback SET feedback=?, rating=? WHERE investor=? AND startup=?",
                  (feedback, rating, investor, startup))
        conn.commit()
        await ctx.response.send_message(
            f"Feedback updated for {investor} from {startup} with a rating of {rating} stars.")
    else:
        await ctx.response.send_message(
            f"Feedback for {investor} from {startup} does not exist. Use `/submitfeedback` to create.")


@tree.command(name = "help", description = "Show this message.")
async def bot_help(ctx: discord.Interaction):
    msg = discord.Embed(title = f"{bot.user.name} - by `@sid110307`",
                        description = "A Discord bot for submitting feedback for investors.", color = 0x00ff00)
    msg.add_field(name = "/submitfeedback <investor> <feedback>", value = "Submit feedback for an investor.",
                  inline = False)
    msg.add_field(name = "/searchfeedback <investor>", value = "Search for feedback for an investor.", inline = False)
    msg.add_field(name = "/listinvestors", value = "List all investors with feedback.", inline = False)
    msg.add_field(name = "/liststartups", value = "List all startups with feedback.", inline = False)
    msg.add_field(name = "/deletefeedback <investor>", value = "Delete feedback for an investor.", inline = False)
    msg.add_field(name = "/startupfeedback <startup>", value = "List all feedback given by a startup.", inline = False)
    msg.add_field(name = "/investorfeedback <investor>", value = "List all feedback for an investor.", inline = False)
    msg.add_field(name = "/updatefeedback <investor> <feedback>", value = "Update feedback for an investor.",
                  inline = False)
    msg.add_field(name = "/help", value = "Show this message.", inline = False)

    await ctx.response.send_message(embed = msg)


if __name__ == "__main__":
    try:
        token = os.environ.get("DISCORD_API_KEY")
        if token is None:
            raise ValueError("DISCORD_API_KEY environment variable is not set.")

        bot.run(str(token))
    except KeyboardInterrupt:
        print("Exiting... ", end = "")
        print("Done.")
    finally:
        conn.close()
