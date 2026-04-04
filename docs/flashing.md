# Flashing Potato OS

Step-by-step guide for flashing Potato OS to a microSD card using Raspberry Pi Imager.

## What you need

- Raspberry Pi 5 (8 GB or 16 GB)
- microSD card (16 GB minimum)
- Power supply (20W USB-C minimum, 27W recommended if using a USB SSD)
- Ethernet or Wi-Fi connection (for first-boot model download)
- A computer with [Raspberry Pi Imager](https://www.raspberrypi.com/software/) installed

## Flash with Raspberry Pi Imager

### 1. Open Raspberry Pi Imager

Launch Raspberry Pi Imager. You will see the device selection screen. Click **App Options** in the bottom left.

<img src="assets/install_steps/01-device-selection.jpg" alt="Device selection screen" width="680">

### 2. Add the Potato OS repository

In the App Options dialog, click **Edit** next to **Content Repository**.

<img src="assets/install_steps/02-app-options.jpg" alt="App Options dialog" width="680">

Select **Use custom URL** and paste the following manifest URL:

```
https://github.com/potato-os/core/releases/download/stable/potato-lite.rpi-imager-manifest
```

Click **Apply & Restart**.

<img src="assets/install_steps/03-content-repository-url.jpg" alt="Content Repository URL" width="680">

### 3. Select your device

Imager restarts and shows **"Using data from github.com"** in the title bar. Only Raspberry Pi 5 is listed since that is what Potato OS supports. Select it and click **Next**.

<img src="assets/install_steps/04-imager-restarted.jpg" alt="Imager restarted with Potato OS data" width="680">

### 4. Select Potato OS

Choose **Potato OS (lite, Raspberry Pi 5)** — it shows as recommended. Click **Next**.

<img src="assets/install_steps/05-os-selection.jpg" alt="OS selection" width="680">

### 5. Select your microSD card

Pick your microSD card from the list. Make sure you select the right one — all data on it will be erased. Click **Next**.

<img src="assets/install_steps/06-storage-selection.jpg" alt="Storage selection" width="680">

### 6. Customise settings

The Imager walks you through five customisation screens. Fill in each one and click **Next**.

**Hostname** — Set this to `potato`. This is required for `http://potato.local` to work on your network.

<img src="assets/install_steps/07-hostname.jpg" alt="Hostname setting" width="680">

**Localisation** — Pick your time zone and keyboard layout.

<img src="assets/install_steps/08-localisation.jpg" alt="Localisation setting" width="680">

**User account** — Set the username to `pi` and password to `raspberry` (or choose your own). You will need these to SSH into the Pi.

<img src="assets/install_steps/09-user-account.jpg" alt="User account setting" width="680">

**Wi-Fi** — Enter your Wi-Fi network name and password. The Pi needs internet access on first boot to download the starter model. Skip this if you are using Ethernet.

<img src="assets/install_steps/10-wifi.jpg" alt="Wi-Fi setting" width="680">

**SSH** — Enable SSH and select **Use password authentication**. This lets you connect to the Pi remotely.

<img src="assets/install_steps/11-ssh.jpg" alt="SSH setting" width="680">

### 7. Review and write

Review your choices. When everything looks right, click **Write**.

<img src="assets/install_steps/12-write-summary.jpg" alt="Write summary" width="680">

A confirmation dialog warns that all data on the card will be erased. Click **I UNDERSTAND, ERASE AND WRITE**.

<img src="assets/install_steps/13-erase-confirm.jpg" alt="Erase confirmation" width="680">

### 8. Wait for writing to finish

The Imager downloads the image and writes it to the card. Do not disconnect the card while this is in progress.

<img src="assets/install_steps/14-writing-progress.jpg" alt="Writing in progress" width="680">

### 9. Done

When writing is complete, the card is ejected automatically. Remove it from your computer.

<img src="assets/install_steps/15-write-complete.jpg" alt="Write complete" width="680">

## First boot

1. Insert the flashed microSD card into your Pi 5
2. Connect power and network (Ethernet or the Wi-Fi you configured above)
3. Wait for the Pi to boot — this takes a minute or two on the first start
4. Open `http://potato.local` in a browser on the same network

On first boot, Potato OS automatically starts downloading a starter model — **Qwen3.5-2B** (~1.8 GB), a small but capable language model that runs well on Pi 5 hardware. A 5-minute countdown timer is shown before the download begins, giving you time to cancel if you want to skip it or load a different model later. Download speed depends on your internet connection. Once the download finishes and the model loads, the status shows **CONNECTED** and you can start chatting.

## Alternative: download and flash manually

If you prefer not to use the content repository flow:

1. Download the latest `.img.xz` from [Releases](https://github.com/potato-os/core/releases)
2. Open Raspberry Pi Imager → **Choose OS** → scroll to bottom → **Use custom** → select the downloaded file
3. Follow steps 5–9 above

Or flash with `dd` (macOS/Linux — replace `/dev/diskN` with your SD card):

```bash
xz -dc potato-lite-*.img.xz | sudo dd of=/dev/rdiskN bs=4m
```

## Troubleshooting

**`potato.local` doesn't open:**
- Make sure the Pi finished booting (give it 2–3 minutes on first start)
- Check that the Pi and your browser are on the same network
- Verify the hostname was set to `potato` during customisation
- Try the Pi's IP address directly if mDNS is not working on your network

**Model download seems stuck:**
- The first-boot download is ~1.8 GB — on a slow connection it can take a while
- Check `http://potato.local` for the download progress bar
- If it fails, the UI shows a retry option

**Need to start over:**
- See [recovery.md](recovery.md) for reflashing and rollback instructions

## Updating

Potato OS is currently reflash-only — there is no OTA or in-place upgrade path. To move to a newer version, reflash the card with the latest image from [Releases](https://github.com/potato-os/core/releases).
