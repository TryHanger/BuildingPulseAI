# G5.2 · Источник и лицензия

Ghalamsiah et al., Scientific Data 13:15, 9 января 2026, DOI 10.1038/s41597-025-06179-y. Использован открытый полный текст в PMC и опубликованный паспорт внутри набора. Релиз Figshare 29297999 v3, дата версии 18 августа 2025, лицензия CC BY 4.0. Статья и выпуск данных датированы отдельно. [Статья в PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12796274/), [Figshare v3](https://doi.org/10.6084/m9.figshare.29297999.v3), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## Приёмка байтов

| Идентичность | Значение |
|---|---|
| Figshare file ID | 57268553 |
| Официальный объект | Public_ScientificData_AHUFaults.zip |
| Размер объекта | 928 675 992 байта |
| Publisher MD5 | `5649a042ba05462ff01b1c32f5b7788b`, из API метаданных, не пересчитан для полного объекта |
| SHA-256 снимка Figshare JSON | `cddf899807e954b59e6ca57108b57d6c48515e8d59656a824c8df89c3afd0586` |
| HTTP identity | Ответы 206 с проверенным диапазоном, размером объекта и стабильным multipart ETag `bcb61029cf69043da14c2279ef575db3-9` |
| Передано для G36-5wk | 2 871 031 байт в подтверждённой выборочной выгрузке, включая хвост каталога |
| Передано для G36-1wk probe | 2 278 137 байт для двух членов, включая хвост каталога |

Издательский ZIP целиком не загружался. ETag не является MD5 объекта. Открыты и проверены CRC всех пяти нужных членов G36-5wk и двух членов G36-1wk probe. SHA-256 рассчитан по неизменённым распакованным байтам каждого файла. Ряды открыты CSV-парсером, паспорта прочитаны. [Figshare API](https://api.figshare.com/v2/articles/29297999), [официальный файл](https://ndownloader.figshare.com/files/57268553)

| G36-5wk member | Байты | SHA-256 |
|---|---:|---|
| 00_explanations.pdf | 436787 | `0b8131fa4a4aa09bbe9cd035ab428df099e24a066ab9163e828db0b80889a5af` |
| BaselineSystem.csv | 6025065 | `fe744430e7800d6d33847137346032501e63f0cd30fec6bef9b41b0f8ec1569d` |
| CooCoiValStuck_0.csv | 6089351 | `b71d2aa060bd126376848c2826e4990f53986b3f665b2c670c75ad01ebef0ff9` |
| OADamStuck_100.csv | 6023976 | `18dd3dbc16adead32dc9233b408b42462994a353c4badc1c5efe409977f610b0` |
| SupDucLea_20.csv | 5239529 | `793fc4819831b71bd065c549f9a8903a8ee86391b5f80ec207ba74ccf5ebce46` |

Отдельный артефакт исходных байтов **BUILDINGPULSE_G5_2_G36_SOURCE_BYTES.zip**, 4 854 638 байт, SHA-256 `fb9ad25e4bad4f2299c70bb63d0a2bb4e1806883c175cd8dbae57c5c268d324f`. В нём файлы G36-5wk и два probe-члена с атрибуцией издателя и SHA каждого файла. Для Investigator нужны только первые два CSV номинального и выбранного прогона. Архив с кодом содержит метаданные, квитанции и результаты.

Полные пути внутри издательского ZIP и CRC — в `outputs/G36_5WK_MEMBER_RECEIPT.json` и `outputs/G36_1WK_MEMBER_RECEIPT.json`. Снимок публичного каталога 1wk — `outputs/G36_1WK_DIRECTORY.json`.
