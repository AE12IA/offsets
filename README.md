<p align="center">
  <img src="images/banner1.jpg" alt="Roblox FFlag Offsets Banner" width="70%" />
</p>

<h1 align="center">fflag-offsets</h1>

<p align="center">
  <b>Up-to-date and historical Roblox FFlag/offset dumps for modding, scripting, and research purposes.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/github/last-commit/AE12IA/fflag-offsets?style=for-the-badge" alt="Last Commit">
  <img src="https://img.shields.io/badge/Roblox-FFlags-brightgreen?style=for-the-badge" alt="FFlags">
  <img src="https://img.shields.io/github/issues/AE12IA/fflag-offsets?style=for-the-badge" alt="Issues">
</p>

---

## 🚩 Overview

**fflag-offsets** is a repository providing Roblox FFlag (Feature Flag) memory offsets for every Roblox client version.  
Dumped offsets enable advanced scripting, automation, and research tools to function across Roblox updates.

<p align="center">
  <img src="images/demo-fflags-dump.png" alt="Sample FFlag Dump Output" width="60%">
</p>

---

## ✨ Features

- 🛠️ **Automatic Offsets Dumper**  
  Included Python script automatically extracts FFlag offsets from the running Roblox client.

- 📦 **Multi-language Output**  
  Exports as C++ (`offsets.hpp`), JSON (`offsets.json`), Python (`offsets.py`), and C# (`Offsets.cs`).

- 🕑 **Full Version Archive**  
  Every Roblox version gets its own branch (e.g., `version-xxxxxxxxxxxxxxxx`). Always have historical offsets at your fingertips.

- ⚡ **Fastest Updates Possible**  
  Just run, dump, commit—keep up with every Roblox release.

---

## 📥 Getting Started

**1. Get the latest offsets:**  
Download or view `offsets.json`, `offsets.hpp`, `offsets.py`, or `Offsets.cs` from the `main` branch.

**2. Get offsets for an older version:**  
Switch to the [branches list](../../branches) and find the proper version branch (`version-xxxxxxxxxxxxxxxx`). All offset files are preserved there.

<p align="center">
  <img src="images/version-branches.png" alt="Offsets Version Branches" width="70%">
</p>

**3. Query versions automatically:**  
Use the [GitHub branches API](https://api.github.com/repos/AE12IA/fflag-offsets/branches) to list every available version programmatically.

---

## 🔄 Updating Offsets

1. Let Roblox auto-update as normal.
2. Run `main.py` while Roblox is open to dump the latest offsets.
3. Commit new offsets to `main`.
4. Before updating for the next version, create a new branch for the current version (`version-xxxxxxxxxxxxxxxx`). This keeps old offsets available.

---

## 🧩 Prefixes

- `prefixes.json` contains a reference of all recognized FFlag/FInt/FString/etc. prefixes.
- Regenerate and update this file every time you dump new offsets after a Roblox update.

---

## 🤝 Contributing

Pull requests and feedback are very welcome!  
Feel free to add patches for new formats, bug fixes, or documentation improvements.

---

## 📚 Credits

- Automated dumper and repo: [AE12IA](https://github.com/AE12IA)
- Inspired by Discord/Roblox reverse engineering communities.
- Special thanks to all contributors.

---

## 📄 License

For educational and research use. See `LICENSE` for details.

---

<p align="center">
  <img src="images/thanks.png" alt="Thank You" width="120">
</p>
