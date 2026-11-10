# نظام قناة الرعب: Make (موجود عندك) + Render Free + YouTube API

**القناة المحددة مسبقًا:** https://youtube.com/channel/UC7DQ1Bd-smHjVQxAtN-1eTg

هذه نسخة تشغيل تجريبية فعلية لخدمة ويب تستقبل أمرًا صغيرًا من Make، فتكتب قصة رعب بواجهة Gemini المجانية، وتحوّل النص إلى تعليق عربي عبر Piper، وتصنع الفيديو عبر FFmpeg، وتحاول رفعه إلى قناة يوتيوب الصحيحة عبر OAuth. لا تمر ملفات الفيديو داخل Make، ولذلك لا تتأثر بحجم الملفات الأقصى فيه. يُنتَج فيديو أفقي وآخر عمودي عند اختيار `both`.

**الحقيقة المهمة:** من دون اشتراك أو بطاقة بنكية يمكن نشر هذه النسخة على Render Free، لكن الخدمة تحصل على **0.1 vCPU و512MB RAM فقط**، وقد تتوقف بعد 15 دقيقة من الخمول وتفقد ملفات العمل المؤقتة أو تُعاد تشغيلها. **لم يتم التحقق من نجاح إنتاج فيديو طويل فعلي على Render Free**؛ ملفات الفيديو الجاهزة للاختبار في هذا المشروع ليست ضمانًا لاستمرار التشغيل. كذلك جودة الصور الاحتياطية رسوم ثابتة، وليست مشاهد سينمائية AI.

## الإعداد الأول (مرة واحدة؛ لا تُرسل مفاتيحك إلى المحادثة)

1. أنشئ مستودع GitHub خاصًا من الملفات المرفقة في ZIP بعد فكّ الضغط، ولا ترفع أي ملفات أسرار. مستودع GitHub للتخزين والنشر فقط؛ لا نستخدم GitHub Actions لتوليد المحتوى.
2. ادخل إلى https://dashboard.render.com/ ثم `New > Blueprint` واختر المستودع. تحقّق من وجود `plan: free` في `render.yaml` قبل الموافقة؛ لا تُضف أي بطاقة دفع.
3. في Render > Service > Environment ستجد `AUTOMATION_KEY` الذي وُلّد عشوائيًا. خزّنه دون مشاركته، ثم أضف بنفسك باقي المتغيرات المذكورة أدناه. أنشئ مفتاح Gemini من https://aistudio.google.com/apikey ضمن Free Tier، وضعه في `GEMINI_API_KEY`. مفتاح Pixabay اختياري من https://pixabay.com/api/docs/ في `PIXABAY_API_KEY`.
4. في https://console.cloud.google.com/ أنشئ مشروعًا بدون تفعيل Billing، وفعّل `YouTube Data API v3` ثم انتقل إلى `Google Auth Platform > Clients` وأنشئ `Web application`. اجعل Authorized redirect URI مطابقًا بالضبط لـ `https://YOUR-SERVICE.onrender.com/oauth/callback`، واستبدل YOUR-SERVICE بعنوان خدمتك الحقيقي. أضف `YOUTUBE_CLIENT_ID` و`YOUTUBE_CLIENT_SECRET` إلى Render. قد يتطلب Google خطوات OAuth إضافية أو يعرض تحذير تطبيق غير مُتحقق منه.
5. لحماية صلاحية الدخول المستمر، إن كان التطبيق External في حالة `Testing` ستنتهي صلاحية Refresh Token عادة بعد 7 أيام. راجع `Google Auth Platform > Audience` لنقله إلى `In production` عندما يكون ذلك متاحًا وملائمًا للسياسات؛ التطبيق الشخصي قد يظهر تحذير تطبيق غير متحقق منه.
6. افتح `https://YOUR-SERVICE.onrender.com/connect`، أدخل `AUTOMATION_KEY`، ووافق على ربط Google. الخدمة ستتحقق من أن Google أرجع قناة `UC7DQ1Bd-smHjVQxAtN-1eTg` **قبل عرض رمز الاتصال**. انسخ الرمز إلى متغير Render `YOUTUBE_REFRESH_TOKEN`. لا تصور الرمز أو تشاركه.

## اختبار مجاني قبل النشر

من Make Scenario الحالي يمكنك إضافة `HTTP > Make a request` فقط. للاختبار: `POST https://YOUR-SERVICE.onrender.com/run`، واجعل Body `Raw > JSON` بالقيمة:

```json
{"mode":"short","publish":false,"dry_mock":true}
```

وأضف Header: `X-Automation-Key` بقيمة `AUTOMATION_KEY` المخزّنة في Render، و`Content-Type: application/json`.

**اختبار mock لا ينتج تعليقًا عربيًا صالحًا للنشر؛ وإنما يختبر تركيب MP4 فقط.** اختبار الإنتاج الحقيقي قبل الرفع:

```json
{"mode":"short","publish":false,"dry_mock":false}
```

تابع Render Logs أو `GET /status` بالـHeader نفسه. عند النجاح سيظهر الملف في Render في `output/` لكن ملفات Render ليست دائمة، وقد لا يمكنك تنزيلها من الخطة المجانية مباشرة؛ الأهم هو نجاح مراحل الإنتاج في Logs.

## تفعيل الرفع التلقائي (بعد نجاح الاختبارات)

1. اجعل `ENABLE_AUTOPUBLISH=true` داخل Render Environment.
2. في Make سيناريو `HTTP > Make a request` استبدل الجسم بـ `{"mode":"both","publish":true}` واجعل السيناريو مجدولًا مرتين أسبوعيًا (مثل الثلاثاء والجمعة الساعة الثانية ظهرًا بالقاهرة)، ثم فعّل السيناريو.
3. الخدمة ستتحقق من هوية القناة قبل بدء الإنتاج، وتنتج نسختين: 854x480 أفقي و480x854 رأسي، بجودة محدودة لتخفيف الحمل على الخطة المجانية، وتجدول الطويل الساعة 8 مساءً والشورت الساعة 8 مساءً في اليوم التالي.
4. راقب YouTube Studio وRender Logs لأول نشر. **العملية ليست مضمونة دون انقطاع على Render Free بسبب محدودية المعالج وإمكان نوم/إعادة تشغيل الخدمة.** لا تستخدم خدمة للنشر الكثيف قبل التأكد من ثباتها.

## الحدود الفعلية

- Make Free: حد معالجة ملفات 5MB — نحن نتفاداه بإرسال أوامر JSON صغيرة فقط.
- Render Free: 0.1 CPU / 512MB RAM، قد ينتهي تشغيل فيديو 5–10 دقائق بالفشل، ولا يسمح بضمان نشر منتظم. ليس مستوى إنتاج.
- Google Gemini: Free Tier بحدود استهلاك قابلة للتغيير. لا تفعل فوترة مدفوعة.
- Piper: تعليق عربي آلي من صوت `ar_JO-kareem-medium`؛ رخصة الصوت راجع ملفات المصدر قبل الربح التجاري.
- Pixabay: لقطات مخزنة مرخصة وفق شروط الاستخدام، ومفتاح اختياري. بدونها ينتج رسومًا مظلمة ثابتة أصلية.
- YouTube: قصة خيالية أصلية وليست مقطعًا منسوخًا. المحتوى الآلي المتكرر منخفض الجودة قد لا يكون مؤهلًا لتحقيق الدخل.

## لم يتم إنجازه بعد

هذا حِزمة نشر واختبار، **وليس خدمة متصلة بقناتك الآن**. لكي أرفع على قناتك يلزم موافقتك على ربط Google وإنشاء الخدمة في حسابك. اختُبرت الوحدات الأساسية محليًا بوضع Mock، لكن **لم يُختبر الرفع الحقيقي أو جودة صوت Piper على Render Free**، ولذلك لا يوجد ادعاء بأن كل شروط التشغيل المستمر تحققت.

## المصادر الرسمية

- https://render.com/docs/compute-plans
- https://render.com/docs/free
- https://help.make.com/working-with-files
- https://developers.google.com/youtube/data/reference/rest/v3/videos/insert
- https://developers.google.com/identity/protocols/oauth2
- https://support.google.com/youtube/answer/1311392
