# Using Agent KitKat from your iPhone

Agent KitKat runs on your Windows computer. Your iPhone opens it in Safari over your home Wi-Fi.
Nothing goes through the internet, so the phone can only use it while the computer is on, awake
and running Agent KitKat.

## Basic setup (plain http)

1. Start Agent KitKat with `start.bat` and keep both windows open. Your phone talks to the
   **frontend** window (port 5173), which passes API calls on to the backend. The backend
   itself only listens on this computer (`127.0.0.1`).
2. Connect the iPhone to the same Wi-Fi as the computer.
3. On the computer, open **Settings → Use it from your iPhone** and copy the address
   (for example `http://192.168.1.23:5173`).
4. Open that address in Safari on the iPhone.
5. Tap **Share → Add to Home Screen**. It opens full-screen like an app.

If Safari can't connect:

* Windows may have asked whether Node.js can use the network the first time `npm run dev` ran.
  Allow it on **Private** networks (Windows Security → Firewall → Allow an app).
* Make sure your Wi-Fi is set as a **Private** network in Windows, not Public.
* The address changes if your router gives the computer a new IP. Reserve the IP in your
  router's DHCP settings to keep it fixed.

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
