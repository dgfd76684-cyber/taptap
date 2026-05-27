# Tap Necklace first-bind demo

This prototype simulates the recommended NFC necklace flow:

1. The necklace is shipped with one unique tap URL already written into NFC.
2. A first tap opens an unbound necklace page.
3. The buyer registers or logs in and the necklace binds to that account.
4. The buyer edits WeChat and Douyin details.
5. Later taps open the public social profile.

## Local routes

- `/` shows the simulation entry.
- `/tap/bekfe` simulates a buyer tapping a fresh necklace with NFC ID `bekfe`.
- `/account` is the returning-owner login and profile editor entry.
- `/u/<profile-slug>` still works for direct preview, but the main public route is the NFC ID route.

## Local backend

`server.py` uses Python standard-library HTTP handling and SQLite:

- `users` stores demo accounts.
- `sessions` stores local login sessions.
- `necklaces` maps an NFC token to its owner.
- `profiles` stores the public page fields.

Start it with:

```powershell
py .\server.py
```

Then open:

```text
http://127.0.0.1:4173/
```

The demo page has a reset button that releases `bekfe` so the first-bind flow can be tested again.

## Going live

- GitHub Pages can host the static front end, but it cannot run `server.py`.
- This project needs a public backend for login, claim, and profile saving.
- For a real custom domain like `taptap.xin`, deploy the backend to a public host first, then point DNS to that host.
- `server.py` reads `HOST`, `PORT`, and `DATABASE_PATH` from environment variables, so it can bind to `0.0.0.0` and keep SQLite on a mounted disk in production.

### Recommended deployment path

1. Push this folder to a GitHub repository.
2. Create a Render Web Service from that repo.
3. Use `render.yaml` or set the start command to `python server.py`.
4. In Render, mount a persistent disk at `/var/data` so `DATABASE_PATH=/var/data/tap_necklace.sqlite3` survives restarts.
5. After Render gives you a public URL, add a CNAME record in Aliyun DNS:
   - host: `@` or `www` depending on the domain setup
   - value: the Render hostname
6. If you want `taptap.xin` to open the site directly, configure the root domain in Render and follow the DNS instructions it shows.

## Product direction

In production, each physical NFC tag should contain a stable prewritten URL like:

```text
https://your-domain.com/tap/A8K2M7
```

When the token is unbound, show onboarding. When it is bound, redirect or render the owner's public profile. Profile edits should happen in the backend and should not require rewriting the tag.
