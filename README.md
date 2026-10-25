# Instagram Book-Summary Bot (free stack)

Roz **3 reels + 1 carousel** apne aap banta aur post hota hai. Aapka circular photo har reel aur carousel par watermark hai.

```
GitHub Actions (cron)
  -> Gemini: Hindi script (book summary, apne shabdon mein)
  -> edge-tts: Hindi voiceover (hi-IN-MadhurNeural)
  -> Pexels: stock footage
  -> FFmpeg: captions + aapka watermark + voice
  -> Cloudinary: temporary public URL
  -> Instagram API: post
```

Sab free hai. Kharcha: 0 rupaye (free tiers ke andar).

## Voiceover (4 free engines, auto-fallback)
Bot is order mein try karta hai, jo pehla chale wahi use hota hai (log mein `voiceover engine: ...` dikhta hai):

| # | Engine | Awaaz | Note |
|---|---|---|---|
| 1 | edge-tts | Madhur (male) / Swara (female) | Sabse achhi free Hindi. Kabhi-kabhi cloud IPs par block ho sakti hai |
| 2 | Gemini TTS | Charon, Puck (male) / Kore (female) | Sabse natural, wahi `GEMINI_API_KEY`. Free limit kam hai, isliye backup |
| 3 | gTTS | Female | Hamesha chalti hai, thodi flat |
| 4 | espeak-ng | Robotic | Offline, last resort taaki posting kabhi na ruke |

Ek fix karna ho to secret `TTS_PROVIDER` = `edge` / `gemini` / `gtts` / `espeak`. Gemini ki awaaz badalne ke liye `GEMINI_TTS_VOICE`.
**Sabse natural option:** apni awaaz. Script `output/*.json` mein milti hai, record karke bhejo to main use video mein laga dunga.

## Posting schedule (IST)

| Time | Kya |
|---|---|
| 07:30 | Reel |
| 13:00 | Reel |
| 17:30 | Carousel |
| 20:00 | Reel |

Badalna ho to `.github/workflows/post.yml` mein cron lines badlo (GitHub cron UTC mein hota hai, IST = UTC + 5:30).

---

## One-time setup (sirf ek baar, ~45 min)

### 1. Instagram ko Professional account banao
Instagram app > Settings > Account type and tools > Switch to professional account > **Creator**.

### 2. Meta Developer app (Instagram API with Instagram Login)
1. https://developers.facebook.com par login > **My Apps > Create App**.
2. Use case: **Manage messaging & content on Instagram** (Meta ka menu thoda badalta rehta hai, jo isse milta-julta ho wo lo).
3. App dashboard > **Instagram > API setup with Instagram login**.
4. **Generate access tokens** > **Add account** > apne Instagram se login karo > **Generate token**.
   Permissions: `instagram_business_basic`, `instagram_business_content_publish`.
5. Wahin se do cheezein copy karo: **Instagram user ID** aur **access token**.
   - Agar token short-lived ho, to long-lived mein badlo (browser mein ye URL kholo, values bharkar):
     `https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=APP_SECRET&access_token=SHORT_TOKEN`
   - App "Development mode" mein rehne do. Apne hi account par post karne ke liye app review nahi chahiye.

### 3. Free API keys
| Kya | Kahan se | Secret ka naam |
|---|---|---|
| Gemini | https://aistudio.google.com/apikey | `GEMINI_API_KEY` |
| Pexels | https://www.pexels.com/api/ | `PEXELS_API_KEY` |
| Cloudinary | https://cloudinary.com (Dashboard par cloud name, API key, API secret) | `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` |

### 4. GitHub par project daalo
1. github.com par naya **private** repo banao (private mein 2000 free Actions minutes/mahina milte hain, ye project lagbhag 400-500 use karta hai).
2. Is folder ko usme push karo:
   ```bash
   cd ig-bot
   git init && git add . && git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/YOUR_NAME/YOUR_REPO.git
   git push -u origin main
   ```

### 5. Secrets daalo
Repo > **Settings > Secrets and variables > Actions > New repository secret**

Zaroori: `GEMINI_API_KEY`, `PEXELS_API_KEY`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `IG_USER_ID`, `IG_ACCESS_TOKEN`, `IG_HANDLE` (jaise `@yourname`, last slide par dikhega).

Optional: `TTS_VOICE` (`hi-IN-SwaraNeural` female ke liye), `TTS_RATE` (`+10%` tez bolne ke liye), `GEMINI_MODEL`, `GH_PAT` (token auto-refresh ke liye, neeche dekho).

### 6. Pehle dry run karo (post nahi hoga)
Repo > **Actions > Post to Instagram > Run workflow** > kind = `reel`, dry_run = **true**.
Khatam hone par run page ke **Artifacts** se `dry-run-output` download karo. Video dekho: awaaz, captions, watermark theek hain?
Phir `carousel` ke saath bhi karo.

### 7. Live jao
Same workflow, `dry_run` = false se ek baar chalao. Instagram par post dikhe to schedule apne aap chalne lagega.

---

## Token ka dhyan (important)
Instagram token **60 din** mein expire hota hai. Do tareeke:
- **Auto:** ek GitHub fine-grained token banao (is repo ke liye, permission *Secrets: Read and write*) aur `GH_PAT` secret mein daalo. `refresh-token.yml` mahine mein 2 baar token renew kar dega.
- **Manual:** har ~50 din mein naya token generate karke `IG_ACCESS_TOKEN` update karo.

Token expire hua to workflow fail hoga aur GitHub aapko email bhejega.

## Customize
- **Watermark badalna:** `assets/watermark.png` replace karo (transparent PNG).
- **Background music:** copyright-free `.mp3` files `assets/music/` mein daalo (sirf wahi jinki license allow kare). Ye halki awaaz mein voice ke peeche chalegi. Khali chhodo to bina music ke banega.
- **Books badhana:** `assets/books.json` mein `{"title": "...", "author": "..."}` jodo. Bot sabse kam use hui book pehle uthata hai aur pichhle hooks se alag angle leta hai.
- **Local test (internet ke saath):** `pip install -r requirements.txt`, FFmpeg + Hindi font install karo, env variables set karo, phir `python -m src.main reel --dry-run`.

## Zaroori sach
- **Growth guaranteed nahi hai.** 1 lakh followers 1 saal mein hook quality, consistency aur niche par depend karta hai. Pehle 30 din ka data dekho (kaun si reel pe retention/shares zyada) aur `REEL_FORMATS` / prompts usi hisaab se tune karo (`src/script_gen.py`).
- **Pure AI/stock content ka risk:** Instagram repetitive, low-effort content ki reach kam kar sakta hai. Hafte mein 1-2 reels apni asli awaaz ya face ke saath dalna growth ke liye bahut madad karta hai.
- **Comments/DM ko automate mat karo.** Auto-comment ya auto-DM bots Instagram ke rules ke khilaaf hain aur account ban karwa sakte hain. Roz 15-20 min khud replies dena sabse zyada kaam ka hai.
- **Copyright:** prompts book ko apne shabdon mein summarize karne ko kehte hain, quotes/paragraph copy nahi. Phir bhi kabhi-kabhi output padh lena achha rehta hai.
- edge-tts ki awaaz AI jaisi lagti hai. Revenue aane par ElevenLabs jaise paid voice par jaana asaan hai (`src/voice.py` mein ek function badalna hai).
- Meta ke API versions aur Gemini ke model names badalte rehte hain. Error aaye to `GRAPH_VERSION` (default `v26.0`) aur `GEMINI_MODEL` secrets/env se update karo.
- Reels 30 sec ke aas-paas bante hain. Agar voice 42 sec se lambi nikli to log mein warning aati hai; `TTS_RATE` badha do.
