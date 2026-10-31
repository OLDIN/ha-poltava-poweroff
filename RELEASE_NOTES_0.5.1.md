# Release 0.5.1

Released: 2026-10-31

## 🐛 Bug Fixes

- The schedule disappeared ("no outages today") when energy-ua.info came back after its downtime without data: an empty hourly scale under "Немає даних" is now treated as "no data", and the last known schedule stays

## ✨ Features

- The schedule now comes from the official Poltavaoblenergo site (poe.pl.ua) first, with energy-ua.info as a fallback when poe.pl.ua is unreachable or has no schedule for today
- When both sites are down, the error names both of them

## 🔄 Update Instructions

1. Update via HACS or manually pull the latest version
2. Restart Home Assistant
