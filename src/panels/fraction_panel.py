import discord
from discord.ui import Button, View
from common.config import id_fraction_category, id_staff_role, ticket_creators, fraction_color
from common.views import TicketInsideView

class CreateFractionView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Создать обращение", style=discord.ButtonStyle.success, emoji='📢', custom_id="create_fraction")
    async def create_fraction_button(self, interaction, button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, id=id_fraction_category)
        rol_staff = discord.utils.get(guild.roles, id=id_staff_role)
        
        # Создание обращения
        channel = await guild.create_text_channel(name=f'📢┃{interaction.user.name}-ticket-ad-fr', category=category)
        
        await channel.set_permissions(channel.guild.default_role,
                        send_messages=False,
                        read_messages=False)
        await channel.set_permissions(interaction.user, 
                            send_messages=True,
                            read_messages=True,
                            add_reactions=True,
                            embed_links=True,
                            attach_files=True,
                            read_message_history=True,
                            external_emojis=True)
        await channel.set_permissions(rol_staff,
                            send_messages=True,
                            read_messages=True,
                            add_reactions=True,
                            embed_links=True,
                            attach_files=True,
                            read_message_history=True,
                            external_emojis=True,
                            manage_messages=True)
        
        ticket_creators[channel.id] = interaction.user
        
        # Сообщение в канале
        embed_fraction = discord.Embed(
            title=f'**Реклама фракций** — ¡Здравствуйте, {interaction.user.name}!', 
            description='Опишите Вашу фракцию для рекламы!\n\nЕсли Ваше обращение является неотложным или Вы ожидаете ответа слишком долго, пожалуйста, нажмите `🔔 Позвать на помощь`.', 
            color=fraction_color 
        )
        embed_fraction.set_thumbnail(url=interaction.user.display_avatar.url)
        
        view = TicketInsideView()
        await channel.send(interaction.user.mention, embed=embed_fraction, view=view)
        await interaction.response.send_message(f'> Обращение {channel.mention} создано для решения Вашего вопроса.', ephemeral=True)
