import discord
from discord.ext import commands
from discord import app_commands # مكتبة الأوامر المائلة (Slash Commands)
import os
from keep_alive import keep_alive 
import asyncio
import json
import yt_dlp
import random

# -------------------------------------------------------------------------
# الدوال المساعدة لإدارة ملف settings.json
# -------------------------------------------------------------------------

SETTINGS_FILE = 'settings.json'

def load_settings():
    """تحميل الإعدادات من ملف JSON"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_settings(settings):
    """حفظ الإعدادات إلى ملف JSON"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

# -------------------------------------------------------------------------
# كلاس الأزرار التفاعلية (AzkarView)
# -------------------------------------------------------------------------

class AzkarView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.update_buttons_from_settings()

    def update_buttons_from_settings(self):
        self.clear_items() 
        settings = load_settings()
        azkar_data = settings.get('azkar_buttons', {})

        for key, data in azkar_data.items():
            style_map = {'blue': discord.ButtonStyle.blurple, 'red': discord.ButtonStyle.red, 'green': discord.ButtonStyle.green, 'grey': discord.ButtonStyle.secondary}

            button = discord.ui.Button(
                label=data['label'],
                style=style_map.get(data['style'], discord.ButtonStyle.secondary),
                custom_id=f"azkar_{key}"
            )
            button.callback = self.create_button_callback(data['content'])
            self.add_item(button)

    def create_button_callback(self, content):
        async def callback(interaction: discord.Interaction):
            await interaction.response.send_message(
                f"**📋 الأذكار المطلوبة:**\n\n{content}",
                ephemeral=True
            )
        return callback

# -------------------------------------------------------------------------
# إعدادات البوت (Intents)
# -------------------------------------------------------------------------

# تفعيل النوايا الضرورية
intents = discord.Intents.default()
intents.message_content = True 
intents.members = True 
intents.guilds = True       
intents.moderation = True   
intents.presences = True    

# إزالة البادئة التقليدية لإجبار استخدام /slash commands
bot = commands.Bot(command_prefix='_', intents=intents)
tree = app_commands.CommandTree(bot)

# -------------------------------------------------------------------------
# الأحداث (Events)
# -------------------------------------------------------------------------

@bot.event
async def on_ready():
    settings = load_settings()
    if settings.get('azkar_buttons'):
        bot.add_view(AzkarView(bot))

    # تسجيل أوامر الـ Slash Commands
    await tree.sync() 

    print('----------------------------------')
    print(f'✅ البوت جاهز! تم تسجيل الدخول باسم: {bot.user}')
    await bot.change_presence(activity=discord.Game(name="استخدم /مساعدة"))
    print('----------------------------------')

@bot.event
async def on_member_join(member):
    settings = load_settings()
    embed_data = settings.get('welcome_embed', {})

    # //////////////////// تذكر تعديل اسم القناة هنا //////////////////////
    channel = discord.utils.get(member.guild.channels, name='اسم-القناة-الترحيب') 

    # رسالة الترحيب
    if channel and embed_data:
        embed = discord.Embed(
            title=embed_data.get('title', 'مرحباً!'),
            description=f"أهلاً بك يا {member.mention}! {embed_data.get('description', '')}",
            color=embed_data.get('color', discord.Color.blue())
        )
        image_url = embed_data.get('image_url')
        if image_url and image_url != 'https://example.com/default_welcome_image.png':
            embed.set_image(url=image_url)

        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # نظام الردود التلقائية
    settings = load_settings()
    responses = settings.get('auto_responses', {})

    content_lower = message.content.lower()

    for keyword, response in responses.items():
        if keyword.lower() in content_lower:
            await message.channel.send(response)
            return # يرسل رداً واحداً ثم يتوقف

    # معالجة الأوامر التقليدية إذا كنت قد أبقيت أي بادئة
    await bot.process_commands(message)

# -------------------------------------------------------------------------
# أوامر الإدارة (Admin Slash Commands)
# -------------------------------------------------------------------------

@tree.command(name='بان', description='حظر عضو من السيرفر.')
@app_commands.describe(member='العضو المراد حظره', reason='سبب الحظر')
@app_commands.checks.has_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يحدد"):
    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ لا يمكنك حظر نفسك.", ephemeral=True)
        return
    await member.ban(reason=reason)
    await interaction.response.send_message(f'🔨 تم حظر {member.mention} بنجاح. السبب: {reason}')

@tree.command(name='كيك', description='طرد عضو من السيرفر.')
@app_commands.describe(member='العضو المراد طرده', reason='سبب الطرد')
@app_commands.checks.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يحدد"):
    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ لا يمكنك طرد نفسك.", ephemeral=True)
        return
    await member.kick(reason=reason)
    await interaction.response.send_message(f'👋 تم طرد {member.mention} بنجاح. السبب: {reason}')


@tree.command(name='ارسال_embed', description='يرسل رسالة Embed مخصصة لأي قناة.')
@app_commands.describe(
    channel_id='آيدي القناة المستهدفة', 
    title='عنوان الرسالة (استخدم _ للمسافات)', 
    color_hex='كود اللون بالـ Hex (مثل FF5733)', 
    description='محتوى الرسالة (استخدم _ للمسافات)'
)
@app_commands.checks.has_permissions(administrator=True)
async def send_custom_embed_slash(interaction: discord.Interaction, channel_id: str, title: str, color_hex: str, description: str):

    try:
        channel_id_int = int(channel_id)
        channel = bot.get_channel(channel_id_int)

        if not channel:
            await interaction.response.send_message(f"❌ لم أجد القناة بالـ ID: `{channel_id}`.", ephemeral=True)
            return

        color_hex = color_hex.lstrip('#')
        embed_color = int(color_hex, 16)

        embed = discord.Embed(
            title=title.replace('_', ' '),
            description=description.replace('_', ' '),
            color=embed_color
        )
        embed.set_footer(text=f"تم الإرسال بواسطة: {interaction.user.display_name}")

        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ تم إرسال رسالة Embed بنجاح إلى قناة: **#{channel.name}**.", ephemeral=True)

    except ValueError:
        await interaction.response.send_message("❌ آيدي القناة أو كود اللون غير صالح. تأكد من إدخال الأرقام وكود Hex صحيح.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ أثناء الإرسال: {e}", ephemeral=True)


@tree.command(name='مسح', description='يمسح عدداً محدداً من الرسائل.')
@app_commands.describe(amount='عدد الرسائل المراد مسحها')
@app_commands.checks.has_permissions(manage_messages=True)
async def clear_slash(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    await interaction.response.defer(ephemeral=True) 
    await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"✅ تم مسح {amount} رسالة بنجاح.", ephemeral=False)

@tree.command(name='تعديل_الترحيب', description='يعدل رسالة الترحيب.')
@app_commands.describe(
    title='العنوان (استخدم _ للمسافات)', 
    color_hex='كود اللون (Hex)', 
    image_url='رابط الصورة (إذا لا يوجد ضع None)', 
    description='الوصف (استخدم _ للمسافات)'
)
@app_commands.checks.has_permissions(administrator=True)
async def modify_welcome_slash(interaction: discord.Interaction, title: str, color_hex: str, image_url: str, description: str):

    settings = load_settings()

    try:
        color_int = int(color_hex.lstrip('#'), 16)
    except ValueError:
        await interaction.response.send_message("❌ كود اللون غير صالح. استخدم كود Hex بدون # (مثل FF00FF).", ephemeral=True)
        return

    settings['welcome_embed'] = {
        'title': title.replace('_', ' '),
        'description': description.replace('_', ' '),
        'color': color_int,
        'image_url': image_url if image_url.lower() != 'none' else None
    }
    save_settings(settings)

    await interaction.response.send_message("✅ تم تحديث رسالة الترحيب بنجاح. سيتم تطبيق الإعدادات الجديدة عند انضمام عضو جديد.", ephemeral=True)

# -------------------------------------------------------------------------
# أوامر إدارة الأذكار (Azkar Commands)
# -------------------------------------------------------------------------

@tree.command(name='إدارة_اذكار', description='إضافة/حذف/نشر أزرار الأذكار التفاعلية.')
@app_commands.describe(
    action='(add/remove/publish)',
    key='مفتاح الزر (مثال: morning)',
    label='تسمية الزر (مثال: أذكار_الصباح)',
    style='لون الزر (blue/red/green/grey)',
    content='محتوى الأذكار الذي سيظهر (استخدم _ للمسافات)'
)
@app_commands.checks.has_permissions(administrator=True)
async def manage_azkar_buttons_slash(interaction: discord.Interaction, action: str, key: str = None, label: str = None, style: str = None, content: str = None):

    settings = load_settings()
    azkar_data = settings.get('azkar_buttons', {})

    if action.lower() == 'add':
        if not all([key, label, style, content]):
            await interaction.response.send_message("❌ الرجاء تقديم المفتاح والتسمية والستايل والمحتوى للإضافة.", ephemeral=True)
            return

        valid_styles = ['blue', 'red', 'green', 'grey']
        if style.lower() not in valid_styles:
            await interaction.response.send_message(f"❌ ستايل غير صالح. المتاح: {', '.join(valid_styles)}", ephemeral=True)
            return

        azkar_data[key] = {
            'label': label.replace('_', ' '),
            'style': style.lower(),
            'content': content.replace('_', ' ')
        }
        settings['azkar_buttons'] = azkar_data
        save_settings(settings)
        await interaction.response.send_message(f"✅ تم إضافة زر الأذكار `{label.replace('_', ' ')}` بنجاح.", ephemeral=True)

    elif action.lower() == 'remove':
        if not key:
            await interaction.response.send_message("❌ الرجاء تقديم مفتاح الزر للحذف.", ephemeral=True)
            return

        if key in azkar_data:
            del azkar_data[key]
            settings['azkar_buttons'] = azkar_data
            save_settings(settings)
            await interaction.response.send_message(f"✅ تم حذف زر الأذكار ذو المفتاح `{key}` بنجاح.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ المفتاح `{key}` غير موجود.", ephemeral=True)

    elif action.lower() == 'publish':
        if not azkar_data:
            await interaction.response.send_message("❌ لا توجد أزرار أذكار مضافة حالياً لنشرها.", ephemeral=True)
            return

        view = AzkarView(bot)
        view.update_buttons_from_settings()

        embed = discord.Embed(
            title="✨ مكتبة الأذكار والأدعية ✨",
            description="اضغط على الزر الذي تريده لتظهر لك الأذكار في رسالة خاصة.",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, view=view)

    else:
        await interaction.response.send_message("❌ أمر إدارة غير صالح. استخدم: `add`, `remove`, أو `publish`.", ephemeral=True)


# -------------------------------------------------------------------------
# أوامر إدارة الردود التلقائية (Auto-Responder Commands)
# -------------------------------------------------------------------------

@tree.command(name='إدارة_ردود', description='إضافة/حذف ردود تلقائية.')
@app_commands.describe(
    action='(add/remove/list)',
    keyword='الكلمة المفتاحية (لا مسافات)',
    response='الرد الذي سيرسله البوت'
)
@app_commands.checks.has_permissions(administrator=True)
async def manage_auto_responses_slash(interaction: discord.Interaction, action: str, keyword: str = None, response: str = None):
    settings = load_settings()
    responses_data = settings.get('auto_responses', {})
    action = action.lower()

    if action == 'add':
        if not keyword or not response:
            await interaction.response.send_message("❌ لاستخدام `add`: يجب تحديد كلمة مفتاحية ورد.", ephemeral=True)
            return

        responses_data[keyword] = response
        settings['auto_responses'] = responses_data
        save_settings(settings)
        await interaction.response.send_message(f"✅ تم إضافة رد تلقائي: **{keyword}** -> **{response}**", ephemeral=True)

    elif action == 'remove':
        if not keyword:
            await interaction.response.send_message("❌ لاستخدام `remove`: يجب تحديد الكلمة المفتاحية للحذف.", ephemeral=True)
            return

        if keyword in responses_data:
            del responses_data[keyword]
            settings['auto_responses'] = responses_data
            save_settings(settings)
            await interaction.response.send_message(f"✅ تم حذف الرد التلقائي للمفتاح: **{keyword}**", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ الكلمة المفتاحية **{keyword}** غير موجودة.", ephemeral=True)

    elif action == 'list':
        if not responses_data:
            list_msg = "لا توجد ردود تلقائية مضافة حالياً."
        else:
            list_msg = "**📋 قائمة الردود التلقائية:**\n" + "\n".join([f"`{k}` -> {v}" for k, v in responses_data.items()])

        await interaction.response.send_message(list_msg, ephemeral=True)

    else:
        await interaction.response.send_message("❌ أمر إدارة غير صالح. استخدم: `add`, `remove`, أو `list`.", ephemeral=True)


# -------------------------------------------------------------------------
# أوامر الموسيقى (Music Slash Commands)
# -------------------------------------------------------------------------

# نفس خيارات YDL_OPTIONS
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'auto'
}

@tree.command(name='انضمام', description='يدخل البوت إلى القناة الصوتية.')
async def join_slash(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"✅ انضممت إلى القناة الصوتية: **{channel.name}**")
    else:
        await interaction.response.send_message("❌ يجب أن تكون في قناة صوتية أولاً لتتمكن من تشغيلي.", ephemeral=True)

@tree.command(name='شغل', description='يبحث ويشغل أغنية من يوتيوب.')
@app_commands.describe(query='اسم أو رابط الأغنية')
async def play_slash(interaction: discord.Interaction, query: str):
    await interaction.response.defer() # تأخير الرد لأن العملية تستغرق وقتاً

    if not interaction.guild.voice_client:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
        else:
            await interaction.followup.send("❌ يجب أن تكون في قناة صوتية أولاً.", ephemeral=True)
            return

    try:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]

            audio_url = next(f['url'] for f in info['formats'] if f.get('ext') == 'm4a' or f.get('ext') == 'webm' and f.get('acodec') != 'none')

            source = discord.FFmpegPCMAudio(audio_url)

            if interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.stop()

            interaction.guild.voice_client.play(source, after=lambda e: print(f'خطأ في التشغيل: {e}') if e else None)
            await interaction.followup.send(f"🎶 يتم تشغيل: **{info.get('title', 'عنوان غير معروف')}**")

    except Exception as e:
        print(f"حدث خطأ في التشغيل: {e}")
        await interaction.followup.send("❌ حدث خطأ أثناء محاولة تشغيل الأغنية. تأكد من أن الرابط أو العنوان صالح.")


@tree.command(name='خروج', description='يوقف التشغيل ويغادر القناة الصوتية.')
async def leave_slash(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 غادرت القناة الصوتية بنجاح.")
    else:
        await interaction.response.send_message("❌ أنا لست في قناة صوتية حالياً.", ephemeral=True)


# -------------------------------------------------------------------------
# أوامر الألعاب والتفاعل (Games & Interaction Slash Commands)
# -------------------------------------------------------------------------

@tree.command(name='كتات', description='يعرض اقتباساً عشوائياً وحكمة جميلة.')
async def quotes_slash(interaction: discord.Interaction):

    quotes_list = [
        "إذا أردت أن تعيش سعيداً، انظر إلى من هو دونك في العافية والرزق، لا من هو فوقك.", "الناجحون يبحثون دائماً عن الفرص لمساعدة الآخرين، بينما الفاشلون يسألون: ماذا أستفيد أنا؟", "لا تستعجل الأمور قبل أوانها، فلكل شيء قدر، ولكل قدر وقت.", "الشخص الذي يثق في نفسه لا يحتاج إلى أن يثبت شيئاً للآخرين.", "ما فاتك لم يخلق لك، وما خلق لك لن يفوتك.", "الفرق بين النجاح والفشل هو القدرة على الاستمرار بعد الفشل.", "لا تحكم على مسيرتي، فأنت لم تسر في دروبي ولم تعش أيامي.", "العقل القوي يكمن في الجسم القوي، والجسم القوي يكمن في الغذاء الصحي.", "التغيير لا يأتي إلا من داخلك أنت، فكن أنت صانع مستقبلك.", "لا تجعل خوفك يقرر مصيرك.", "الإنجاز هو أن تجعل ما هو صعب سهلاً، وما هو سهل ممكناً.", "الشجاعة ليست غياب الخوف، بل هي القدرة على التغلب عليه.", "المستحيل هو كلمة اخترعها الضعفاء.", "الوقت كالسيف، إن لم تقطعه قطعك.", "ليس عليك أن تكون عظيماً لتبدأ، ولكن عليك أن تبدأ لتكون عظيماً.", "الابتسامة هي مفتاح لكل الأبواب المغلقة.", "تذكر دائماً أنك لست وحدك، فالله معك في كل خطوة.", "الأمل هو الكنز الوحيد الذي يرفض الزمن أن يسرقه منا.", "افعل شيئاً صعباً، لكن افعله بروح حماسية.", "النجاح ليس النهاية، والفشل ليس قاتلاً، إنها الشجاعة للاستمرار هي ما يهم.", "الكتب هي أفضل الأصدقاء، لا تخون ولا تجادل.", "الأشياء التي نملكها هي التي تملكنا إذا سمحنا لها بذلك.", "الخسارة لا تعني الفشل، بل تعني فرصة للتعلم من جديد.", "أهم شيء هو ألا تتوقف عن السؤال. الفضول له سبب وجوده الخاص.", "عليك أن تفعل الأشياء التي تعتقد أنك لا تستطيع فعلها.", "الذكاء الحقيقي لا يكمن في المعرفة، بل في الخيال.", "لا تبكِ على ما فات، بل ابتسم لما هو آت.", "العقبات هي تلك الأشياء المخيفة التي تراها عندما ترفع عينيك عن هدفك.", "أفضل طريقة للتنبؤ بالمستقبل هي اختراعه.", "الجمال يكمن في طريقة رؤيتك للأشياء.", "القوة ليست في أن تمتلك، بل في أن تمنح.", "الجهد الذي تبذله اليوم هو ما سيحدد نجاحك غداً.", "لا أحد يستطيع أن يجعلك تشعر بالنقص دون موافقتك.", "الإنسان ينمو عندما يواجه التحديات، لا عندما يتجنبها.", "إذا لم تكن راضياً عن مكانك، غيّر مكانك، أنت لست شجرة.", "الحياة قصيرة جداً لتقضيها في محاولة إرضاء الجميع.", "ابنِ أحلامك على الواقع، لكن لا تدع الواقع يقتل أحلامك.", "التفكير الزائد مضيعة للوقت والطاقة.", "الفرق بين الواقع والخيال هو أن الخيال يجب أن يكون منطقياً.", "الفشل هو فرصة لتبدأ من جديد بذكاء أكبر.", "ثق بنفسك، فأنت تعرف أكثر مما تعتقد.", "القاعدة الذهبية: عامل الناس كما تحب أن يعاملوك.", "كل يوم هو صفحة جديدة في كتاب حياتك.", "لا تخف من المضي قدماً ببطء، خف فقط من الوقوف ساكناً.", "التعلم هو الكنز الذي سيتبع صاحبه أينما ذهب.", "السعادة ليست شيئاً جاهزاً، بل تأتي من أفعالك.", "من يزرع المعروف يحصد الشكر.", "لا يوجد أسرار للنجاح، النجاح هو نتاج الإعداد والعمل الجاد والتعلم من الفشل.", "المعرفة قوة، ولكن الشخصية هي المفتاح.", "الأبطال لا يصنعون في الصالات الرياضية، الأبطال يصنعون مما في داخلهم من رغبة وحلم ورؤية.", "الشخص الذي يقرأ كثيراً، يرى العالم بطريقة مختلفة.", "العمل الجماعي هو القدرة على العمل معاً نحو رؤية مشتركة.", "الإخلاص هو أعلى درجات الصدق.", "إذا لم تخاطر بشيء، فإنك تخاطر بكل شيء.", "استغل الفرص قبل أن تصبح مجرد ذكريات.", "الصبر مفتاح الفرج.", "لا تسعَ لتكون ناجحاً، بل لتكون ذا قيمة.", "التعليم هو أقوى سلاح يمكنك استخدامه لتغيير العالم.", "الإيمان بالله يضيء العتمة ويهون الصعاب.", "إذا سقطت سبع مرات، فانهض في الثامنة.", "العبقرية هي 1% إلهام و 99% عرق وجهد.", "الفرق بين الحلم والهدف هو وجود خطة واضحة وموعد نهائي.", "لا تنتظر الوقت المناسب، الوقت المناسب لا يأتي أبداً.", "أكثر الناس حكمة هم الذين يعترفون بأنهم لا يعرفون.", "توقف عن مطاردة المال، وابدأ بمطاردة النجاح.", "السعادة الحقيقية تكمن في متعة الإنجاز.", "الشكوى هي أول خطوة نحو الفشل.", "أصدقاؤك هم عائلتك التي تختارها.", "اجعل حياتك قصة تستحق أن تروى.", "عندما تغرب الشمس اليوم، لا تنسَ أنك تعلمت شيئاً جديداً.", "لا تفكر في كيفية الانتهاء، فكر فقط في كيفية البدء.", "الماضي لا يساوي المستقبل.", "نحن لا نتوقف عن اللعب لأننا كبرنا، بل نكبر لأننا توقفنا عن اللعب.", "أعطِ الناس الأمل، وستحصل على كل شيء.", "أن تكون إيجابياً لا يعني أنك لا تشعر بالحزن، بل يعني أنك تعلم أن الحزن مؤقت.", "قوتك تكمن في قدرتك على التعافي من سقطاتك.", "المعجزات تحدث لمن يصرون على الإيمان بها.", "الحياة لا تصبح أسهل، بل نحن نصبح أقوى.", "إذا أردت أن ترى قوس قزح، عليك أن تتحمل المطر.", "الإيجابية هي أن ترى الضوء في نهاية النفق، لكن الإصرار هو أن تستمر في المشي نحوه.", "أكبر مخاطرة في الحياة هي ألا تخاطر بشيء أبداً.", "لا تندم على شيء علّمك درساً.", "التقدير هو أساس كل علاقة ناجحة.", "القلب الذي لا يحمل حقداً، هو قلب سعيد.", "تعلّم أن تصغي، فالصمت يمنحك الحكمة.", "لا تضيع لحظة واحدة في الندم، فالندم لا يغير الماضي.", "النجاح ليس مفتاح السعادة، السعادة هي مفتاح النجاح.", "اجعل من الأمس درساً، ومن اليوم تجربة، ومن الغد أملاً.", "التواضع هو السمة المميزة للعظماء.", "ابدأ صغيراً، لكن فكّر كبيراً.", "الشخص الذي يبتسم لا يعني أنه سعيد، بل يعني أنه قوي.", "الكلمات مثل المفاتيح، إذا اخترتها بشكل صحيح، يمكنك أن تفتح بها أي عقل أو قلب.", "لا تستخدم الماضي كعذر لتدمير حاضرك ومستقبلك.", "السفر يجعلك تعرف كم أنت صغير في هذا العالم الواسع.", "لا تكن نسخة من أحد، كن فريداً.", "النجاح هو رحلة، وليس وجهة.", "أهم استثمار تفعله هو استثمارك في نفسك.", "إذا فشلت في التخطيط، فقد خططت للفشل.", "السرعة ليست مهمة، الاستمرار هو كل شيء.", "الحياة هي ما يحدث لك وأنت مشغول بالتخطيط لأشياء أخرى."
    ]

    quote = random.choice(quotes_list)

    embed = discord.Embed(
        title="🌟 اقتباس عشوائي | حكم وواقع 🌟",
        description=f"**\" {quote} \"**",
        color=discord.Color.teal() 
    )
    embed.set_footer(text="أرسل /كتات للحصول على المزيد من الإيجابية.")

    await interaction.response.send_message(embed=embed)


@tree.command(name='روليت', description='يراهن على لون عشوائي في لعبة الروليت.')
@app_commands.describe(bet='قيمة الرهان (رقم موجب)')
async def roulette_slash(interaction: discord.Interaction, bet: app_commands.Range[int, 1, None]):

    outcomes = {'أحمر': 2, 'أسود': 2, 'أخضر': 35}
    result = random.choices(list(outcomes.keys()), weights=[47.37, 47.37, 5.26], k=1)[0]

    embed = discord.Embed(title="🎰 لعبة الروليت", color=0x000000 if result == 'أسود' else 0xFF0000 if result == 'أحمر' else 0x008000)

    if result == 'أخضر':
        win = bet * 35
        embed.description = f"الكرة استقرت على **اللون الأخضر**! 🎉\nلقد فزت بمبلغ خيالي: **{win} نقطة!**"
    elif result == 'أحمر' or result == 'أسود':
        win = bet * 2
        embed.description = f"الكرة استقرت على **{result}**! 🏆\nلقد فزت بـ **{win} نقطة!**"
    else:
        win = 0
        embed.description = f"الكرة استقرت على **{result}**! 📉\nللأسف، خسرت **{bet} نقطة**."

    await interaction.response.send_message(embed=embed)

# متغير لتتبع الألعاب
mafia_games = {} 

@tree.command(name='مافيا', description='بدء لعبة المافيا المطورة (Mafia Extra).')
@app_commands.describe(min_players='الحد الأدنى للبدء (يوصى بـ 6)')
async def mafia_slash(interaction: discord.Interaction, min_players: app_commands.Range[int, 4, 15]):

    if interaction.guild_id in mafia_games and mafia_games[interaction.guild_id]['status'] != 'finished':
        await interaction.response.send_message("❌ توجد لعبة مافيا نشطة بالفعل في هذا السيرفر.", ephemeral=True)
        return

    mafia_games[interaction.guild_id] = {
        'host': interaction.user,
        'min_players': min_players,
        'players': {interaction.user.id: interaction.user},
        'status': 'joining',
        'channel': interaction.channel
    }

    embed = discord.Embed(
        title="🎩 لعبة المافيا المطورة (الإصدار الإضافي) 🐺",
        description=f"المضيف: {interaction.user.mention}\nالحد الأدنى للبدء: **{min_players} لاعبين**\n\nاضغط على الزر **'انضم'** للمشاركة! اللعبة تبدأ بعد 60 ثانية أو عند اكتمال العدد.",
        color=0x4B0082 # بنفسجي داكن
    )

    view = discord.ui.View(timeout=60)

    @discord.ui.button(label="انضم", style=discord.ButtonStyle.green, custom_id="mafia_join")
    async def join_button_callback(button_interaction: discord.Interaction, button: discord.ui.Button):
        game = mafia_games.get(interaction.guild_id)
        if game and game['status'] == 'joining':
            if button_interaction.user.id not in game['players']:
                game['players'][button_interaction.user.id] = button_interaction.user
                await button_interaction.response.send_message(f"✅ انضممت إلى اللعبة! عدد اللاعبين الحالي: **{len(game['players'])}**", ephemeral=True)

                # تحديث الرسالة الأصلية بالعدد
                updated_embed = embed.copy()
                updated_embed.add_field(name="اللاعبون الحاليون:", value=f"**{len(game['players'])}** / {min_players}", inline=False)
                await interaction.edit_original_response(embed=updated_embed, view=view)

                if len(game['players']) >= min_players:
                    view.stop() 
                    await interaction.followup.send("⏳ تم الوصول للحد الأدنى! بدء توزيع الأدوار...")
            else:
                await button_interaction.response.send_message("❌ أنت منضم بالفعل.", ephemeral=True)
        else:
            await button_interaction.response.send_message("❌ انتهى وقت الانضمام أو اللعبة بدأت.", ephemeral=True)

    view.add_item(join_button_callback)

    await interaction.response.send_message(embed=embed, view=view)

    await view.wait()

    # بعد انتهاء الوقت أو اكتمال العدد
    game = mafia_games.get(interaction.guild_id)
    if game and game['status'] == 'joining':
        players_count = len(game['players'])

        if players_count < min_players:
            del mafia_games[interaction.guild_id]
            await interaction.followup.send(f"❌ لم يكتمل العدد الكافي. تم إلغاء لعبة المافيا. (مطلوب {min_players}، الحاضرون {players_count})")
            return

        # ----------------------------------------------------
        # توزيع الأدوار
        # ----------------------------------------------------

        roles = []

        # المافيا (القتل)
        num_mafia = max(1, players_count // 4)
        roles.extend(['مافيا'] * num_mafia)

        # المدنيون (المواطن العادي)
        num_villagers = players_count - num_mafia - 3 # خصم 3 شخصيات دعم

        # شخصيات دعم أساسية (يجب أن يكون العدد كافياً لـ 4 على الأقل)
        roles.append('طبيب') # يحمي شخصاً واحداً في الليل
        roles.append('شريف') # يمكنه التحقيق في الهوية مرة واحدة في الليل
        roles.append('محقق') # يمكنه كشف هوية شخص ما في الليل (محدود)

        # إضافة مواطنين عاديين بعد ذلك
        num_villagers = players_count - len(roles)
        roles.extend(['مواطن'] * num_villagers)

        random.shuffle(roles)

        player_list = list(game['players'].values())
        player_roles = dict(zip(player_list, roles))

        # إرسال الأدوار رسالة خاصة
        for player, role in player_roles.items():
            try:
                await player.send(f"🎭 **دورك في لعبة المافيا:** أنت هو **{role}**!\n\n**القوانين الأساسية:**\n- **المافيا:** مهمتهم القتل في الليل.\n- **الطبيب:** مهمته حماية شخص في الليل.\n- **الشريف:** يمكنه التحقق من هوية مشتبه به.\n- **المواطن:** مهمته كشف المافيا بالنقاش والتصويت في النهار.")
            except discord.Forbidden:
                await interaction.followup.send(f"❌ لم أستطع إرسال الدور إلى {player.mention}. يرجى التأكد من تفعيل الرسائل الخاصة.")

        game['player_roles'] = player_roles
        game['status'] = 'started'

        start_embed = discord.Embed(
            title="⚔️ اللعبة بدأت! ⚔️",
            description=f"تم توزيع الأدوار على **{players_count} لاعبين** في الرسائل الخاصة.\n\n**المرحلة الحالية: النهار (النقاش والتصويت).**\nلديك 5 دقائق للبدء بالنقاش وتحديد من تشكون فيه.",
            color=0x1E90FF
        )
        await interaction.followup.send(embed=start_embed)

@tree.command(name='روليت_روسي', description='محاكاة للعبة الروليت الروسي (فرصة 1/6).')
async def russian_roulette_slash(interaction: discord.Interaction):

    chamber = [False] * 5 + [True]  
    random.shuffle(chamber)

    result = chamber[0]

    embed = discord.Embed(title="🔫 الروليت الروسي", color=0xFF0000)

    if result:
        embed.description = f"**{interaction.user.mention} سحب الزناد...** 💥\nللأسف، لقد خسرت الرهان!"
        embed.color = 0x8B0000
    else:
        embed.description = f"**{interaction.user.mention} سحب الزناد...** 💨\nالطلق كان فارغاً! لقد نجوت هذه المرة."
        embed.color = 0x00FF00

    await interaction.response.send_message(embed=embed)

# قائمة لتتبع الألعاب النشطة (لمنع التداخل)
active_math_games = {} 

@tree.command(name='رياضيات', description='يبدأ تحدي أسئلة حسابية عشوائية.')
async def math_game_slash(interaction: discord.Interaction):

    if interaction.channel_id in active_math_games:
        await interaction.response.send_message("❌ توجد لعبة رياضيات نشطة بالفعل في هذه القناة.", ephemeral=True)
        return

    num1 = random.randint(10, 50)
    num2 = random.randint(2, 20)

    operations = {
        '+': lambda a, b: a + b,
        '-': lambda a, b: a - b,
        '*': lambda a, b: a * b,
        '/': lambda a, b: round(a / b) if a % b == 0 and b != 0 else None
    }
    op_symbol = random.choice(list(operations.keys()))

    if op_symbol == '/':
        if num1 % num2 != 0:
            result = random.randint(2, 10)
            num1 = num2 * result
        correct_answer = num1 / num2
    else:
        correct_answer = operations[op_symbol](num1, num2)

    active_math_games[interaction.channel_id] = correct_answer
    problem_string = f"{num1} {op_symbol} {num2}"

    embed = discord.Embed(
        title="🧠 تحدي الرياضيات",
        description=f"ما ناتج العملية الحسابية التالية؟\n\n## {problem_string} =\n\n**لديك 30 ثانية للإجابة!**",
        color=discord.Color.orange()
    )
    embed.set_footer(text="للإجابة، اكتب الرقم فقط (مثال: 50)")
    await interaction.response.send_message(embed=embed)

    def check(m):
        return m.channel == interaction.channel and not m.content.startswith('/') and m.content.isdigit()

    try:
        guess_msg = await bot.wait_for('message', check=check, timeout=30.0)
        user_guess = float(guess_msg.content)

        if round(user_guess) == round(correct_answer):
            await interaction.channel.send(f"🎉 **إجابة صحيحة يا {guess_msg.author.mention}!** الناتج هو: **{round(correct_answer)}**.")
        else:
            await interaction.channel.send(f"❌ إجابة خاطئة يا {guess_msg.author.mention}. الناتج الصحيح كان: **{round(correct_answer)}**.")

    except asyncio.TimeoutError:
        await interaction.channel.send(f"⏳ انتهى الوقت! لم يقم أحد بالإجابة. الناتج الصحيح هو: **{round(correct_answer)}**.")

    finally:
        if interaction.channel_id in active_math_games:
            del active_math_games[interaction.channel_id]

@tree.command(name='لعبة', description='لعبة حجر ورقة مقص ضد البوت.')
@app_commands.describe(choice='(حجر/ورقة/مقص)')
async def rps_slash(interaction: discord.Interaction, choice: str):

    choices = ['حجر', 'ورقة', 'مقص']
    bot_choice = random.choice(choices)
    user_choice = choice.lower()

    if user_choice not in choices:
        await interaction.response.send_message(f"❌ اختيار غير صالح. يرجى الاختيار من: {', '.join(choices)}", ephemeral=True)
        return

    result = ""
    if user_choice == bot_choice:
        result = "تعادل!"
    elif (user_choice == 'حجر' and bot_choice == 'مقص') or \
         (user_choice == 'ورقة' and bot_choice == 'حجر') or \
         (user_choice == 'مقص' and bot_choice == 'ورقة'):
        result = "أنت الفائز! 🎉"
    else:
        result = "البوت فاز. 🤖"

    await interaction.response.send_message(f"أنت اخترت: **{user_choice}**\nالبوت اختار: **{bot_choice}**\nالنتيجة: **{result}**")


# -------------------------------------------------------------------------
# أمر المساعدة (Help Command)
# -------------------------------------------------------------------------

@tree.command(name='مساعدة', description='يعرض قائمة بجميع أوامر البوت.')
async def help_command_slash(interaction: discord.Interaction):

    embed = discord.Embed(
        title="🤖 دليل أوامر البوت (العملية الأساسية: /)",
        description="جميع الأوامر تبدأ الآن بالشرطة المائلة `/`.",
        color=discord.Color.blue()
    )

    # 1. أوامر الموسيقى
    embed.add_field(name="🎶 أوامر الموسيقى", value="---", inline=False)
    embed.add_field(name="/انضمام", value="يدخل البوت إلى القناة الصوتية.", inline=True)
    embed.add_field(name="/شغل", value="يبحث ويشغل أغنية من يوتيوب.", inline=True)
    embed.add_field(name="/خروج", value="يوقف التشغيل ويغادر القناة الصوتية.", inline=True)

    # 2. أوامر التفاعل والألعاب
    embed.add_field(name="🕹️ التفاعل والألعاب", value="---", inline=False)
    embed.add_field(name="/كتات", value="يعرض اقتباساً عشوائياً وحكمة جميلة.", inline=True) 
    embed.add_field(name="/روليت", value="لعبة روليت كلاسيكية.", inline=True)
    embed.add_field(name="/روليت_روسي", value="محاكاة للعبة الروليت الروسي.", inline=True)
    embed.add_field(name="/مافيا", value="بدء لعبة المافيا المطورة (بشخصيات إضافية).", inline=True)
    embed.add_field(name="/رياضيات", value="يبدأ تحدي أسئلة حسابية عشوائية.", inline=True) 
    embed.add_field(name="/لعبة", value="لعبة حجر ورقة مقص ضد البوت.", inline=True)

    # 3. أوامر الإدارة والترحيب
    embed.add_field(name="⚙️ الإدارة", value="---", inline=False)
    embed.add_field(name="/ارسال_embed", value="يرسل رسالة Embed مخصصة لأي قناة.", inline=True)
    embed.add_field(name="/مسح", value="يمسح عدداً محدداً من الرسائل.", inline=True)
    embed.add_field(name="/بان / /كيك", value="لحظر أو طرد الأعضاء.", inline=True)
    embed.add_field(name="/تعديل_الترحيب", value="لتعديل رسالة/صورة الترحيب.", inline=True)
    embed.add_field(name="/إدارة_اذكار", value="لإضافة/حذف/نشر أزرار الأذكار.", inline=True)
    embed.add_field(name="/إدارة_ردود", value="لإضافة/حذف قائمة الردود التلقائية.", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True) # عرض المساعدة بشكل خاص

# ----------------------------------------------------
# 4. تشغيل البوت
# ----------------------------------------------------

keep_alive()

try:
    bot_token = os.environ.get('TOKEN')
    if not bot_token:
        print("❌ خطأ: لم يتم العثور على توكن البوت في متغير البيئة 'TOKEN'.")
    else:
        bot.run(bot_token)
except Exception as e:
    print(f"❌ حدث خطأ أثناء تشغيل البوت: {e}")
