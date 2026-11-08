# pagh-repo — пакетный репозиторий для pagh-riscv

Здесь лежат **готовые пакеты** для нативного установщика `pkg` в ядре
pagh-riscv. Это не apt и не Debian: формат описан в
[`docs/package-format.md`](docs/package-format.md), пакеты собираются из
[`pagh-programs`](https://github.com/ccclosed/pagh-programs).

## Сейчас

`index` отдаёт `paghbox 1.9.0` (121 команда, 894925 байт,
sha256 `ebd5a44378b2382a540500f6d6e38a2bdcfc9a72e8abfac92ae07697961a054a`);
предыдущие 1.0.0–1.8.0 остаются в `pkg/` для истории.

## Раскладка

```
index                 # индекс: имя, версия, sha256, размер, kind, commands, url
pkg/<name>-<ver>.ppkg # пакеты (ELF + манифест)
docs/package-format.md
tools/publish.py      # принять собранный repo/ из pagh-programs и проверить digests
serve.sh              # локальное HTTP-зеркало для QEMU (10.0.2.2:8000)
```

## Как обновить

```sh
# в pagh-programs
cargo build --release --target riscv64gc-unknown-none-elf
python3 tools/build_repo.py          # создаёт repo/index и repo/pkg/*.ppkg

# здесь
python3 tools/publish.py ../pagh-programs/repo
git add -A && git commit -m "repo: publish <packages>"
git push
```

`publish.py` проверяет, что каждый `index`-строковый sha256/размер совпадает с
пакетом, и только потом копирует.

## Как это скачивается

Пока у порта нет TLS: установщик `pkg` говорит по plain HTTP, поэтому
репозиторий зеркалируется на хосте:

```sh
./serve.sh            # python3 -m http.server 8000 -d .
# в госте (QEMU user network):
pkg repo http://10.0.2.2:8000/
pkg index
pkg install paghbox
```

HTTPS + подписи пакетов (OpenPGP) — следующий майлстоун; до него `pkg`
проверяет только SHA-256/размер из индекса и отказывается устанавливать при
несовпадении. Зеркало без индекса или с битым пакетом отвергается.

## Статус

- [x] формат пакета и индекса зафиксирован (`docs/package-format.md`)
- [x] GitHub-репозиторий создан
- [ ] первый индекс с реальными пакетами (после первых портов)
- [ ] HTTPS/подписи и автоматическая публикация из pagh-programs
