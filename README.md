<div align="center">
    <img src="https://github.com/noaione/potia-muse/raw/master/assets/avatar.png" alt="Avatar" width="300" height="300">
    <h2>Potia</h2>
    <p>Sebuah bot pengurus peladen resmi Muse Indonesia</p>
</div>

### **[po.tia](https://kbbi.kemdikbud.go.id/entri/potia)**<br />
_**n Cn**_ mandor; pengawas

## Requirements
- Python 3.6+
- Hosting bot

Bot yang dijalankan di peladen resmi bukanlah bot publik yang bisa diinvite siapa saja.<br />
Semua fitur yang dijelaskan di sini membutuhkan modifikasi berat jika ingin di deploy pribadi.<br />

## Setup
1. Clone repository ini dan masuk ke foldernya:
    - `git clone https://github.com/noaione/potia-muse.git`
    - `cd potia-muse`
2. Buatlah sebuah virtualenv baru dengan cara: `virtualenv env`
3. Masuk ke virtualenv situ:
    - Windows: `.\env\Scripts\activate`
    - Linux/Mac: `source ./env/bin/activate`
4. Install semua requirements dengan cara: `pip install -r requirements.txt`
5. Rename `config.json.example` menjadi `config.json` dan isi.
6. Run bot dengan cara `python bot.py`

## Fitur
- *Welcome message* dengan gambar kustom
- Mirror semua informasi upload dan stream di YouTube ke sebuah kanal di Discord
- **TODO**: Mirror postingan dari Twitter dan Youtube community
- Fitur untuk laporan kopi kanan (Copyright IP Infringement)
- **TODO**: Mod logs support (Deleted messages/edit/welcome/leave/etc)
- **TODO**: Moderation tools
