import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

from common.config import *
from common.views import TicketInsideView, ConfirmCloseView
from panels.main_panel import CreateTicketView, TicketMenuView
from panels.fraction_panel import CreateFractionView
from panels.rp_panel import CreateRPView, RPMenuView

load_dotenv()

bot = commands.Bot(command_prefix=os.getenv('BOT_PREFIX'), help_command=None, intents=discord.Intents.all())

# Команды
@bot.command()
@commands.has_permissions(administrator=True)
async def ticket(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title='📝 Обращения', description='Для связи с командой проекта.\n\n📌 Выберите тип обращения и создайте тикет\n⏰ Постараемся ответить как можно быстрее!', color=main_color)
    embed.set_image(url=img)
    view = CreateTicketView()
    await ctx.send(embed=embed, view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def fraction(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title='📢 Реклама фракций', description='Для подачи заявки на рекламу Вашей фракции.\n\n⏰ Постараемся ответить как можно быстрее!', color=fraction_color)
    embed.set_image(url=img)
    view = CreateFractionView()
    await ctx.send(embed=embed, view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def RP(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title='🎭 RP-обращения', description='Для регистрации города, фракции или решения иных RP-вопросов.\n\n📌 Выберите тип обращения и создайте тикет\n⏰ Постараемся ответить как можно быстрее!', color=rp_color)
    embed.set_image(url=img)
    view = CreateRPView()
    await ctx.send(embed=embed, view=view)
    
@bot.event
async def on_ready():
    members = 0
    for guild in bot.guilds:
        members += guild.member_count - 1

    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f'{members} members'
    ))
    
    # Персистентные View
    bot.add_view(CreateTicketView())
    bot.add_view(TicketInsideView())
    bot.add_view(TicketMenuView())
    bot.add_view(CreateFractionView())    
    bot.add_view(CreateRPView())    
    bot.add_view(RPMenuView())      
    
    print('Ready to support ✅')

bot.run(os.getenv('DISCORD_TOKEN'))
