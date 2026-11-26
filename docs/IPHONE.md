# Using Agent KitKat from your iPhone

Agent KitKat runs on your Windows computer. Your iPhone opens it in Safari over your home Wi-Fi.
Nothing goes through the internet, so the phone can only use it while the computer is on, awake
and running Agent KitKat.

## Basic setup (plain http)

1. Start Agent KitKat with `start.bat` and keep both windows open. Your phone talks to the
   **frontend** window (port 5173), which passes API calls on to the backend. The backend
   itself only listens on this computer (`127.0.0.1`).
2. Connect the iPhone to the same Wi-Fi as the computer.
3. On the computer, open **Settings → Phone access**.
4. Scan the QR code with the iPhone camera and open the link in Safari. This opens the app
   **and pairs the phone** in one step. The link carries the access code after `#`, which is
   never sent to the server's logs and is removed from the address bar straight away.
   (No camera? Open the phone address shown there and paste the access code.)
5. Tap **Share → Add to Home Screen**. It opens full-screen like an app.

### Phone access code

Other devices on your Wi-Fi can't use Agent KitKat without the access code; they get a
"Pair this device" screen. The code is created on first start and stored in
`storage/lan_access.json` (never in Git). On the phone it's kept in a cookie that page
scripts can't read.

* **New access code** (Settings → Phone access) unpairs every phone. Use it if a phone is lost.
* **Turn off** refuses every other device, even paired ones. This computer always works.
* Everything about phone access (seeing the code, the QR code, new code, on/off, backups) is
  only available on this computer, never from a phone.

If Safari can't connect:

* Windows may have asked whether Node.js can use the network the first time `npm run dev` ran.
  Allow it on **Private** networks (Windows Security → Firewall → Allow an app).
* Make sure your Wi-Fi is set as a **Private** network in Windows, not Public.
* The address changes if your router gives the computer a new IP. Reserve the IP in your
  router's DHCP settings to keep it fixed.
* Your network doesn't use the usual home ranges (`192.168.x.x`, `10.x.x.x`,
  `172.16–31.x.x`), for example a VPN such as Tailscale (`100.x.x.x`)? Pairing then fails with
  "Cross-site request blocked". Add the phone address to `.env`, for example
  `CORS_EXTRA_ORIGINS=http://100.101.102.103:5173`, and restart.

### What doesn't work over plain http

Browsers only allow service workers on `https://` (or `localhost`). Over plain
`http://<computer-IP>`, iOS won't keep an offline copy of the app shell. Everything else works,
because all data is fetched live from your computer anyway.

## Optional: HTTPS with mkcert (offline shell on the iPhone)

[mkcert](https://github.com/FiloSottile/mkcert) creates a certificate authority that only your
devices trust, and uses it to sign a certificate for your computer's address.

1. Install mkcert on Windows (one of):
   ```powershell
   winget install FiloSottile.mkcert
   # or
   choco install mkcert
   ```
2. Create and trust the local certificate authority on the computer:
   ```powershell
   mkcert -install
   ```
3. Create the certificate in the folder Agent KitKat looks in. Replace `192.168.1.23` with your
   computer's address from Settings:
   ```powershell
   cd <path to Agent.KitKat>
   mkdir frontend\certs
   mkcert -cert-file frontend\certs\cert.pem -key-file frontend\certs\key.pem localhost 127.0.0.1 192.168.1.23
   ```
   `frontend/certs/` and `*.pem` are in `.gitignore`. Never commit them.
4. Trust the certificate authority on the iPhone:
   * Run `mkcert -CAROOT` to find the folder, and send **`rootCA.pem`** (not `rootCA-key.pem`)
     to the iPhone, for example by AirDrop.
   * On the iPhone, install it: **Settings → General → VPN & Device Management** → the downloaded
     profile → Install.
   * Then turn on full trust: **Settings → General → About → Certificate Trust Settings** → enable
     the mkcert certificate.
5. Restart `start.bat`. The frontend now serves `https://`, and **Settings** shows the `https://`
   address. Open it in Safari and add it to the Home Screen again. (If you added the http version
   before, remove that icon.)

**Keep `rootCA-key.pem` private.** Anyone with it can create certificates your devices trust.
If your computer's IP changes, run step 3 again with the new address.

## How updates reach the phone

The app's HTML is loaded from the network first, so a new version shows up the next time you
open it. Built files have unique names per version and are cached. Job, approval and application
data is never cached; it is always read live from your computer.
