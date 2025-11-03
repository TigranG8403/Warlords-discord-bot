import discord
from discord.ui import Button, View
import asyncio
from .config import id_staff_role, ticket_creators, id_channel_ticket_logs, embed_color, get_msk_time, create_transcript

# View для кнопок внутри тикета
class TicketInsideView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Закрыть обращение", style=discord.ButtonStyle.danger, emoji='🔐', custom_id="close_ticket")
    async def close_ticket_button(self, interaction, button):
        embed_close = discord.Embed(description="⚠️ Вы уверены, что хотите закрыть обращение?", color=embed_color)
        view = ConfirmCloseView()
        await interaction.response.send_message(embed=embed_close, view=view, ephemeral=True)
    
    @discord.ui.button(label="Позвать на помощь", style=discord.ButtonStyle.primary, emoji='🔔', custom_id="call_staff")
    async def call_staff_button(self, interaction, button):
        embed_call = discord.Embed(description=f"🔔 {interaction.user.mention} позвал(-а) на помощь.", color=embed_color)
    
        ping_message = await interaction.channel.send(f'<@&{id_staff_role}>')
    
        staff_message = await interaction.channel.send(embed=embed_call)
    
        await interaction.response.send_message("✅ Помощь вызвана!", ephemeral=True)
    
        # Удаление сообщений
        await asyncio.sleep(20)
        try:
            await ping_message.delete()
            await staff_message.delete()
        except:
            pass

# View для подтверждения закрытия тикета
class ConfirmCloseView(View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="Да", style=discord.ButtonStyle.success, custom_id="close_yes")
    async def close_yes_button(self, interaction, button):
        # Проверка на наличие прав (для специальной категории)
        if not await self.can_close_ticket(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав для закрытия этого обращения.", 
                ephemeral=True
            )
            return
        
        canal = interaction.channel
        canal_logs = interaction.guild.get_channel(id_channel_ticket_logs)
        
        ticket_creator = ticket_creators.get(canal.id)
        
        if not ticket_creator:
            for member in canal.members:
                if not member.bot and canal.permissions_for(member).read_messages:
                    ticket_creator = member
                    break
        
        # Создание транскрипта и его файла
        transcript_content = await create_transcript(canal, ticket_creator)
        
        from io import BytesIO
        transcript_bytes = BytesIO(transcript_content.encode('utf-8'))
        current_time = get_msk_time()
        transcript_file = discord.File(
            transcript_bytes, 
            filename=f"transcript_{canal.name}_{current_time.strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        # Лог с транскриптом
        embed_logs = discord.Embed(
            title="Обращения", 
            description="", 
            timestamp=get_msk_time(), 
            color=embed_color
        )
        embed_logs.add_field(name="Обращение", value=f"{canal.name}", inline=True)
        embed_logs.add_field(name="Закрыто", value=f"{interaction.user.mention}", inline=False)
        embed_logs.add_field(name="Транскрипт", value="Прикреплен выше", inline=False)
        embed_logs.set_footer(text="МСК (UTC+3)")
        
        await canal_logs.send(embed=embed_logs, file=transcript_file)
        
        # Отправка транскрипта в ЛС
        if ticket_creator:
            try:
                transcript_bytes_dm = BytesIO(transcript_content.encode('utf-8'))
                
                dm_embed = discord.Embed(
                    title="Транскрипт обращения",
                    description=f"Вот транскрипт Вашего обращения **{canal.name}**, которое было закрыто.",
                    color=embed_color,
                    timestamp=get_msk_time()
                )
                dm_embed.add_field(name="Обращение", value=canal.name, inline=True)
                dm_embed.add_field(name="Закрыто", value=interaction.user.display_name, inline=True)
                dm_embed.set_footer(text="До новых встреч!")
                
                await ticket_creator.send(
                    embed=dm_embed, 
                    file=discord.File(
                        transcript_bytes_dm, 
                        filename=f"transcript_{canal.name}.txt"
                    )
                )
            except discord.Forbidden:
                await canal_logs.send(f"⚠️ Не удалось отправить транскрипт пользователю {ticket_creator.mention} (личные сообщения закрыты)")
            except Exception as e:
                await canal_logs.send(f"❌ Ошибка при отправке транскрипта пользователю {ticket_creator.mention}: {str(e)}")
        else:
            await canal_logs.send(f"⚠️ Не удалось найти создателя обращения {canal.name}")
        
        if canal.id in ticket_creators:
            del ticket_creators[canal.id]
        
        await canal.delete()

    # Функция для проверки на наличие прав    
    async def can_close_ticket(self, interaction):
        channel_name = interaction.channel.name
        
        if any(keyword in channel_name for keyword in ['reg-fr', 'reg-town']):
            admin_permission = interaction.user.guild_permissions.administrator
            has_support_role = any(role.id == id_staff_role for role in interaction.user.roles)
            
            return admin_permission or has_support_role
        
        # Разрешение на закрытие для всех остальных обращений
        return True
    
    @discord.ui.button(label="Нет", style=discord.ButtonStyle.danger, custom_id="close_no")
    async def close_no_button(self, interaction, button):
        await interaction.response.edit_message(content="Закрытие обращения отменено.", embed=None, view=None)
