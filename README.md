# pagh-repo — пакетный репозиторий для pagh-riscv

Здесь лежат **готовые пакеты** для нативного установщика `pkg` в ядре
pagh-riscv. Это не apt и не Debian: формат описан в
[`docs/package-format.md`](docs/package-format.md), пакеты собираются из
[`pagh-programs`](https://github.com/ccclosed/pagh-programs).

## Сейчас

`index` отдаёт `paghbox 1.11.0` (124 команды, 935616 байт,
sha256 `7e3ceac1e0bf45771e4bdaade0d39e5a2e3b4ba09a0303dfea7f888a993b0ee2`);
предыдущие 1.0.0–1.10.0 остаются в `pkg/` для истории.

## Раскладка

```
index                 # индекс: имя, версия, sha256, размер, kind, commands, url
pkg/<name>-<ver>.ppkg # пакеты (ELF + манифест)
docs/package-format.md
tools/publish.py      # принять собранный repo/ из pagh-programs и проверить digests
tools/verify.py       # проверить то, что лежит здесь (индекс + пакеты)
serve.sh              # локальное HTTP-зеркало для QEMU (10.0.2.2:8000)
.github/workflows/ci.yml  # CI: python3 tools/verify.py на push/pull_request
```

## Как обновить

```sh
# в pagh-programs
cargo build --release --target riscv64gc-unknown-none-elf
python3 tools/build_repo.py          # создаёт repo/index и repo/pkg/*.ppkg

# здесь
python3 tools/publish.py ../pagh-programs/repo
python3 tools/verify.py              # то же, что сделает CI
git add -A && git commit -m "repo: publish <packages>"
git push
```

`publish.py` проверяет, что каждый `index`-строковый sha256/размер совпадает с
пакетом, и только потом копирует. `verify.py` (и CI) дополнительно разбирает
заголовок и манифест каждого `.ppkg` — включая исторические версии, которых нет
в индексе, — и сверяет ELF payload с `sha256` манифеста.

## Как это скачивается

Установщик `pkg` пока не умеет TLS: в ядре с 0.21.0 есть userland-TLS-сессии
(`tls_connect`/`tls_read`/`tls_write`), но `pkg` по-прежнему говорит по plain
HTTP, поэтому репозиторий зеркалируется на хосте:

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

## Проверка

```sh
python3 tools/verify.py       # чтение только: ни сборки, ни сети
python3 tools/publish.py ../pagh-programs/repo   # перед публикацией
```

CI (`.github/workflows/ci.yml`) запускает `tools/verify.py` на каждый push и
pull request.

## Статус

- [x] формат пакета и индекса зафиксирован (`docs/package-format.md`)
- [x] GitHub-репозиторий создан
- [x] первый индекс с реальными пакетами (с 1.0.0, сейчас 1.11.0)
- [x] проверка индекса/пакетов в CI (`tools/verify.py`)
- [ ] HTTPS в `pkg` и OpenPGP-подписи пакетов (TLS в ядре есть с 0.21.0;
      установщик ещё на plain HTTP)
- [ ] автоматическая публикация из pagh-programs (сейчас `publish.py` вручную)