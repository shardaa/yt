# Deploying to Oracle Cloud Free Tier

## Step 1: Create a free VM

1. Sign up at https://cloud.oracle.com (credit card required but never charged for free tier)
2. Go to **Compute → Instances → Create Instance**
3. Choose:
   - Shape: **VM.Standard.E2.1.Micro** (Always Free)
   - Image: **Ubuntu 22.04** (or latest)
   - Storage: 47 GB boot volume (free)
4. Download the SSH key pair during creation
5. Note the **Public IP** after the instance launches

## Step 2: Open port 5000 in Oracle Cloud

1. Go to **Networking → Virtual Cloud Networks → your VCN → Security Lists → Default**
2. Add an **Ingress Rule**:
   - Source CIDR: `0.0.0.0/0`
   - Destination Port: `5000`
   - Protocol: TCP

## Step 3: Push your code to a git repo

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/you/youtube-downloader.git
git push -u origin main
```

## Step 4: SSH into your VM and run setup

```bash
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP
curl -O https://raw.githubusercontent.com/you/youtube-downloader/main/deploy/setup-server.sh
bash setup-server.sh
```

## Step 5: Access your app

Open `http://YOUR_PUBLIC_IP:5000` in your browser.

## Updating

After pushing new code:

```bash
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP
bash ~/youtube-downloader/deploy/update-server.sh
```

## Useful commands

```bash
sudo systemctl status ytdownloader    # check status
sudo systemctl restart ytdownloader   # restart
sudo journalctl -u ytdownloader -f    # live logs
```
