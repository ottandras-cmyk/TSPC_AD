(function() {
    var statusElement = document.getElementById('sharepoint-catalog-status');
    var catalogBody = document.getElementById('sharepoint-catalog-body');
    var catalogRefreshButton = document.getElementById('btn-refresh-sharepoint-catalog');
    var dataStatus = document.getElementById('sharepoint-data-status');
    var dataHead = document.getElementById('sharepoint-data-head');
    var dataBody = document.getElementById('sharepoint-data-body');
    var pagination = document.getElementById('sharepoint-data-pagination');
    var dataRefreshButton = document.getElementById('btn-sync-sharepoint-data');
    var imageSyncButton = document.getElementById('btn-sync-sharepoint-images');
    var tableScroll = document.getElementById('sharepoint-table-scroll');
    var horizontalScrollbar = document.getElementById('sharepoint-horizontal-scrollbar');
    var horizontalScrollContent = document.getElementById('sharepoint-horizontal-scroll-content');
    var listNames = ['eszkozleltar_nonIT', 'O365LicenceInfo', 'Atadas_atvetel', 'IT_Inventory'];
    var listLabels = {
        eszkozleltar_nonIT: 'Eszközleltár non-IT',
        O365LicenceInfo: 'O365 licencek',
        Atadas_atvetel: 'Átadás-átvétel',
        IT_Inventory: 'IT Inventory'
    };
    var currentView = 'eszkozleltar_nonIT';
    var currentPage = 1;
    var currentSort = 'sharepoint_item_id';
    var sortDirection = 'asc';
    var pageSize = 50;
    var searchTimer;
    var currentItems = [];
    var currentTotal = 0;
    var currentFieldNames = [];

    var baseColumns = [
        ['sharepoint_item_id', 'SharePoint ID'],
        ['source_modified_at', 'SharePoint módosítva'],
        ['synced_at', 'Helyi frissítve'],
        ['is_deleted', 'Állapot']
    ];

    function getColumnDefinitions(fieldNames) {
        var definitions = baseColumns.concat(fieldNames.map(function(key) {
            return ['field:' + key, key];
        }));
        try {
            var preference = JSON.parse(localStorage.getItem('sharepoint-visible-columns:' + currentView) || '{}');
            var order = Array.isArray(preference.order) ? preference.order : [];
            var available = new Map(definitions.map(function(column) { return [column[0], column]; }));
            var ordered = order.filter(function(key) { return available.has(key); }).map(function(key) {
                var column = available.get(key);
                available.delete(key);
                return column;
            });
            definitions.forEach(function(column) {
                if (available.has(column[0])) {
                    ordered.push(column);
                    available.delete(column[0]);
                }
            });
            return ordered;
        } catch (error) {
            showStatus(dataStatus, 'Az oszlopsorrend nem olvasható: ' + error.message, false);
        }
        return definitions;
    }

    function getVisibleColumnKeys(definitions) {
        var storageKey = 'sharepoint-visible-columns:' + currentView;
        var available = definitions.map(function(column) { return column[0]; });
        var saved;
        try {
            saved = localStorage.getItem(storageKey);
        } catch (error) {
            showStatus(dataStatus, 'Az oszlopbeállítások nem olvashatók a böngésző tárhelyéről: ' + error.message, false);
            return new Set(available);
        }
        if (!saved) return new Set(available);

        try {
            var preference = JSON.parse(saved);
            var selected = new Set();
            (preference.visible || []).forEach(function(key) {
                if (available.indexOf(key) !== -1) selected.add(key);
            });
            available.forEach(function(key) {
                if ((preference.available || []).indexOf(key) === -1) selected.add(key);
            });
            return selected;
        } catch (error) {
            showStatus(dataStatus, 'Az elmentett oszlopbeállítás sérült; az összes oszlop látható.', false);
            return new Set(available);
        }
    }

    function saveVisibleColumns(definitions, visible) {
        try {
            localStorage.setItem('sharepoint-visible-columns:' + currentView, JSON.stringify({
                available: definitions.map(function(column) { return column[0]; }),
                visible: Array.from(visible),
                order: definitions.map(function(column) { return column[0]; })
            }));
            dataStatus.style.display = 'none';
        } catch (error) {
            showStatus(dataStatus, 'Az oszlopbeállításokat nem sikerült elmenteni a böngészőben: ' + error.message, false);
        }
    }

    function renderColumnOptions(definitions, visible) {
        var options = document.getElementById('sharepoint-column-options');
        if (!options) return;
        options.replaceChildren();
        function moveColumn(columnKey, offset) {
            var current = getColumnDefinitions(currentFieldNames);
            var from = current.findIndex(function(column) { return column[0] === columnKey; });
            var to = from + offset;
            if (from < 0 || to < 0 || to >= current.length) return;
            var moved = current.splice(from, 1)[0];
            current.splice(to, 0, moved);
            saveVisibleColumns(current, getVisibleColumnKeys(current));
            renderList(currentItems, currentTotal, currentPage, currentFieldNames);
        }

        definitions.forEach(function(column, index) {
            var option = document.createElement('div');
            option.draggable = true;
            option.dataset.columnKey = column[0];
            option.style.cssText = 'display:flex; align-items:center; gap:4px; padding:3px; border:1px solid #e2e8f0; border-radius:4px; background:white;';
            option.addEventListener('dragstart', function(event) {
                event.dataTransfer.setData('text/plain', column[0]);
                event.dataTransfer.effectAllowed = 'move';
            });
            option.addEventListener('dragover', function(event) {
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
            });
            option.addEventListener('drop', function(event) {
                event.preventDefault();
                var draggedKey = event.dataTransfer.getData('text/plain');
                var current = getColumnDefinitions(currentFieldNames);
                var from = current.findIndex(function(item) { return item[0] === draggedKey; });
                var to = current.findIndex(function(item) { return item[0] === column[0]; });
                if (from < 0 || to < 0 || from === to) return;
                var moved = current.splice(from, 1)[0];
                current.splice(to, 0, moved);
                saveVisibleColumns(current, getVisibleColumnKeys(current));
                renderList(currentItems, currentTotal, currentPage, currentFieldNames);
            });

            var label = document.createElement('label');
            label.style.cssText = 'display:flex; align-items:center; gap:7px; padding:4px; color:#334155; font-size:12px; flex:1; cursor:grab;';
            label.dataset.columnLabel = column[1].toLocaleLowerCase('hu-HU');
            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = visible.has(column[0]);
            checkbox.addEventListener('change', function() {
                var nextVisible = getVisibleColumnKeys(definitions);
                if (checkbox.checked) nextVisible.add(column[0]);
                else nextVisible.delete(column[0]);
                if (nextVisible.size === 0) {
                    checkbox.checked = true;
                    showStatus(dataStatus, 'Legalább egy adat-oszlopot meg kell jeleníteni.', false);
                    return;
                }
                saveVisibleColumns(definitions, nextVisible);
                renderList(currentItems, currentTotal, currentPage, currentFieldNames);
            });
            var text = document.createElement('span');
            text.textContent = column[1];
            label.appendChild(checkbox);
            label.appendChild(text);
            option.appendChild(label);
            [-1, 1].forEach(function(offset) {
                var moveButton = document.createElement('button');
                moveButton.type = 'button';
                moveButton.textContent = offset < 0 ? '↑' : '↓';
                moveButton.title = offset < 0 ? 'Oszlop mozgatása előre' : 'Oszlop mozgatása hátra';
                moveButton.setAttribute('aria-label', moveButton.title + ': ' + column[1]);
                moveButton.disabled = offset < 0 ? index === 0 : index === definitions.length - 1;
                moveButton.style.cssText = 'padding:2px 6px; border:1px solid #cbd5e1; border-radius:4px; background:#f8fafc; cursor:pointer;';
                moveButton.addEventListener('click', function() { moveColumn(column[0], offset); });
                option.appendChild(moveButton);
            });
            options.appendChild(option);
        });
        if (window.filterSharePointColumns) window.filterSharePointColumns();
    }

    function updateHorizontalScrollbar() {
        if (!tableScroll || !horizontalScrollbar || !horizontalScrollContent) return;
        var table = tableScroll.querySelector('table');
        var contentWidth = table ? table.scrollWidth : tableScroll.clientWidth;
        horizontalScrollContent.style.width = Math.max(contentWidth, tableScroll.clientWidth) + 'px';
        horizontalScrollbar.scrollLeft = tableScroll.scrollLeft;
        horizontalScrollbar.style.visibility = contentWidth > tableScroll.clientWidth ? 'visible' : 'hidden';
    }

    if (tableScroll && horizontalScrollbar) {
        tableScroll.addEventListener('scroll', function() {
            if (horizontalScrollbar.scrollLeft !== tableScroll.scrollLeft) {
                horizontalScrollbar.scrollLeft = tableScroll.scrollLeft;
            }
        });
        horizontalScrollbar.addEventListener('scroll', function() {
            if (tableScroll.scrollLeft !== horizontalScrollbar.scrollLeft) {
                tableScroll.scrollLeft = horizontalScrollbar.scrollLeft;
            }
        });
        window.addEventListener('resize', updateHorizontalScrollbar);
        if (window.ResizeObserver) {
            new ResizeObserver(updateHorizontalScrollbar).observe(tableScroll);
        }
        requestAnimationFrame(updateHorizontalScrollbar);
    }

    window.scrollSharePointTable = function(direction) {
        if (!tableScroll) return;
        tableScroll.scrollBy({
            left: direction * Math.max(240, tableScroll.clientWidth * 0.75),
            behavior: 'smooth'
        });
    };

    function formatHistoryValue(value, missingLabel) {
        if (value === undefined) return missingLabel;
        if (value === null) return 'üres';
        return typeof value === 'object' ? JSON.stringify(value) : String(value);
    }

    async function loadItemHistory(container, listName, itemId, page) {
        container.replaceChildren();
        var loading = document.createElement('div');
        loading.textContent = 'Előzmények betöltése...';
        loading.style.cssText = 'padding:10px; color:#64748b;';
        container.appendChild(loading);
        var params = new URLSearchParams({
            list_name: listName,
            item_id: itemId,
            page: String(page),
            page_size: '50'
        });
        try {
            var response = await fetch('/api/settings/sharepoint/changes?' + params);
            var result = await response.json();
            if (!response.ok || result.status !== 'SUCCESS') {
                throw new Error(result.message || result.detail || 'Az elem előzményeinek betöltése nem sikerült.');
            }
            container.replaceChildren();
            if (!result.changes.length) {
                var empty = document.createElement('div');
                empty.textContent = 'Ehhez az elemhez még nincs rögzített változás. Az előzmények a helyi szinkronokból gyűlnek.';
                empty.style.cssText = 'padding:10px; color:#64748b;';
                container.appendChild(empty);
                return;
            }

            result.changes.forEach(function(change) {
                var event = document.createElement('div');
                event.style.cssText = 'padding:10px; border-bottom:1px solid #e2e8f0;';
                var title = document.createElement('strong');
                title.textContent = new Date(change.changed_at).toLocaleString('hu-HU') + ' · ' + change.change_type + ' · ' + change.trigger_type;
                event.appendChild(title);
                var fields = change.changed_fields || [];
                if (!fields.length && change.change_type === 'DELETED') {
                    var deleted = document.createElement('div');
                    deleted.textContent = 'Az elem kikerült a SharePoint-listából.';
                    deleted.style.marginTop = '5px';
                    event.appendChild(deleted);
                }
                fields.forEach(function(field) {
                    var transition = document.createElement('div');
                    transition.style.cssText = 'margin-top:5px; overflow-wrap:anywhere;';
                    var before = (change.previous_fields || {})[field];
                    var after = (change.current_fields || {})[field];
                    transition.textContent = field + ': ' +
                        formatHistoryValue(before, 'korábban nem volt') + ' → ' +
                        formatHistoryValue(after, 'nincs jelen');
                    event.appendChild(transition);
                });
                container.appendChild(event);
            });

            var totalPages = Math.max(1, Math.ceil(result.total / result.page_size));
            if (totalPages > 1) {
                var controls = document.createElement('div');
                controls.style.cssText = 'display:flex; align-items:center; gap:8px; padding:8px;';
                var pageLabel = document.createElement('span');
                pageLabel.textContent = result.page + ' / ' + totalPages + '. oldal';
                controls.appendChild(pageLabel);
                [
                    { label: '← Előző', target: result.page - 1, disabled: result.page <= 1 },
                    { label: 'Következő →', target: result.page + 1, disabled: result.page >= totalPages }
                ].forEach(function(control) {
                    var button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'btn';
                    button.textContent = control.label;
                    button.disabled = control.disabled;
                    button.addEventListener('click', function() {
                        loadItemHistory(container, listName, itemId, control.target);
                    });
                    controls.appendChild(button);
                });
                container.appendChild(controls);
            }
        } catch (error) {
            container.replaceChildren();
            var failure = document.createElement('div');
            failure.textContent = 'Előzménybetöltési hiba: ' + error.message;
            failure.style.cssText = 'padding:10px; color:#b91c1c;';
            container.appendChild(failure);
        }
    }

    async function loadImageVersions(container, itemId) {
        container.replaceChildren();
        var loading = document.createElement('div');
        loading.textContent = 'Képelőzmények betöltése...';
        loading.style.cssText = 'padding:10px; color:#64748b;';
        container.appendChild(loading);
        try {
            var response = await fetch('/api/settings/sharepoint/images/' + encodeURIComponent(itemId));
            var result = await response.json();
            if (!response.ok || result.status !== 'SUCCESS') {
                throw new Error(result.detail || result.message || 'A képelőzmények betöltése nem sikerült.');
            }
            container.replaceChildren();
            var groups = result.image_groups || [];
            if (!groups.length) {
                var empty = document.createElement('div');
                empty.textContent = 'Ehhez a sorhoz még nincs helyben tárolt kép. A képek letöltéséhez használd a fenti frissítés gombot.';
                empty.style.cssText = 'padding:10px; color:#64748b;';
                container.appendChild(empty);
                return;
            }
            groups.forEach(function(group, index) {
                var section = document.createElement('section');
                section.style.cssText = 'padding:10px; border-bottom:1px solid #e2e8f0;';
                var title = document.createElement('strong');
                title.textContent = 'Kép ' + (index + 1) + (group.source_is_current ? ' · jelenleg hivatkozott' : ' · korábbi hivatkozás');
                section.appendChild(title);
                var versions = document.createElement('div');
                versions.style.cssText = 'display:flex; flex-wrap:wrap; gap:10px; margin-top:8px;';
                (group.versions || []).forEach(function(version) {
                    var card = document.createElement('div');
                    card.style.cssText = 'width:150px; padding:8px; border:1px solid #cbd5e1; border-radius:6px; background:white;';
                    var link = document.createElement('a');
                    link.href = version.image_url;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    var image = document.createElement('img');
                    image.src = version.image_url;
                    image.alt = version.file_name + ' – ' + version.version_number + '. verzió';
                    image.loading = 'lazy';
                    image.style.cssText = 'display:block; width:100%; height:90px; object-fit:contain; background:#f8fafc;';
                    link.appendChild(image);
                    card.appendChild(link);
                    var meta = document.createElement('div');
                    meta.style.cssText = 'margin-top:6px; overflow-wrap:anywhere; font-size:11px; color:#334155;';
                    meta.textContent = 'v' + version.version_number + (version.is_latest ? ' · legfrissebb' : '') +
                        ' · ' + new Date(version.downloaded_at).toLocaleString('hu-HU') +
                        ' · ' + Math.ceil(version.file_size_bytes / 1024) + ' KB';
                    card.appendChild(meta);
                    versions.appendChild(card);
                });
                section.appendChild(versions);
                container.appendChild(section);
            });
        } catch (error) {
            container.replaceChildren();
            var failure = document.createElement('div');
            failure.textContent = 'Képelőzmény-betöltési hiba: ' + error.message;
            failure.style.cssText = 'padding:10px; color:#b91c1c;';
            container.appendChild(failure);
        }
    }

    function showStatus(element, message, isSuccess) {
        if (!element) return;
        element.style.display = 'block';
        element.style.background = isSuccess ? '#dcfce7' : '#fee2e2';
        element.style.color = isSuccess ? '#15803d' : '#b91c1c';
        element.style.border = isSuccess ? '1px solid #bbf7d0' : '1px solid #fecaca';
        element.textContent = message;
    }

    function addCell(row, value) {
        var cell = document.createElement('td');
        if (value === null || value === undefined || value === '') {
            cell.textContent = '-';
        } else if (typeof value === 'object') {
            cell.textContent = JSON.stringify(value);
        } else {
            cell.textContent = String(value);
        }
        row.appendChild(cell);
        return cell;
    }

    function setTableMessage(message, colSpan) {
        if (!dataBody) return;
        var row = document.createElement('tr');
        var cell = document.createElement('td');
        cell.colSpan = colSpan || 1;
        cell.textContent = message;
        cell.style.cssText = 'text-align:center; padding:20px; color:#64748b;';
        row.appendChild(cell);
        dataBody.replaceChildren(row);
        if (pagination) pagination.replaceChildren();
    }

    function appendPagination(total, page, endpoint) {
        if (!pagination) return;
        pagination.replaceChildren();
        var summary = document.createElement('span');
        var pages = Math.max(1, Math.ceil(total / pageSize));
        summary.textContent = total + ' elem · ' + page + ' / ' + pages + '. oldal';
        pagination.appendChild(summary);

        var controls = document.createElement('div');
        controls.style.cssText = 'display:flex; gap:7px;';
        [
            { label: '← Előző', target: page - 1, disabled: page <= 1 },
            { label: 'Következő →', target: page + 1, disabled: page >= pages }
        ].forEach(function(control) {
            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn';
            button.textContent = control.label;
            button.disabled = control.disabled;
            button.style.cssText = 'background:#f1f5f9; border:1px solid #cbd5e1; padding:6px 10px;';
            button.addEventListener('click', function() {
                currentPage = control.target;
                endpoint();
            });
            controls.appendChild(button);
        });
        pagination.appendChild(controls);
    }

    function renderList(items, total, page, fieldNames) {
        currentItems = items;
        currentTotal = total;
        currentPage = page;
        currentFieldNames = fieldNames;
        var definitions = getColumnDefinitions(fieldNames);
        var visible = getVisibleColumnKeys(definitions);
        var columns = definitions.filter(function(column) { return visible.has(column[0]); });
        renderColumnOptions(definitions, visible);

        dataHead.replaceChildren();
        var headerRow = document.createElement('tr');
        columns.forEach(function(column) {
            var header = document.createElement('th');
            header.textContent = column[1] + (currentSort === column[0] ? (sortDirection === 'asc' ? ' ▲' : ' ▼') : ' ⇅');
            header.tabIndex = 0;
            header.style.cursor = 'pointer';
            header.addEventListener('click', function() {
                if (currentSort === column[0]) {
                    sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    currentSort = column[0];
                    sortDirection = 'asc';
                }
                currentPage = 1;
                window.loadSharePointData();
            });
            header.addEventListener('keydown', function(event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    header.click();
                }
            });
            headerRow.appendChild(header);
        });
        var historyHeader = document.createElement('th');
        historyHeader.textContent = 'Előzmények';
        headerRow.appendChild(historyHeader);
        if (currentView === 'eszkozleltar_nonIT') {
            var imageHeader = document.createElement('th');
            imageHeader.textContent = 'Képek / verziók';
            headerRow.appendChild(imageHeader);
        }
        dataHead.appendChild(headerRow);
        dataBody.replaceChildren();
        requestAnimationFrame(updateHorizontalScrollbar);

        if (!items.length) {
            setTableMessage('Nincs megjeleníthető rekord ezen a listán.', columns.length + 1 + (currentView === 'eszkozleltar_nonIT' ? 1 : 0));
            return;
        }

        items.forEach(function(item) {
            var row = document.createElement('tr');
            columns.forEach(function(column) {
                var key = column[0];
                var value;
                if (key === 'sharepoint_item_id') value = item.sharepoint_item_id;
                else if (key === 'source_modified_at') value = item.source_modified_at;
                else if (key === 'synced_at') value = item.synced_at ? new Date(item.synced_at).toLocaleString('hu-HU') : '';
                else if (key === 'is_deleted') value = item.is_deleted ? 'Törölt' : 'Aktív';
                else value = (item.fields || {})[key.slice(6)];
                addCell(row, value);
            });
            dataBody.appendChild(row);

            var actionCell = document.createElement('td');
            var historyButton = document.createElement('button');
            historyButton.type = 'button';
            historyButton.className = 'btn';
            historyButton.textContent = '🕘 Előzmények';
            historyButton.style.cssText = 'white-space:nowrap; padding:5px 8px;';
            actionCell.appendChild(historyButton);
            row.appendChild(actionCell);

            var historyRow = document.createElement('tr');
            historyRow.hidden = true;
            var historyCell = document.createElement('td');
            historyCell.colSpan = columns.length + 1 + (currentView === 'eszkozleltar_nonIT' ? 1 : 0);
            historyCell.style.cssText = 'padding:0; background:#f8fafc;';
            var historyContainer = document.createElement('div');
            historyCell.appendChild(historyContainer);
            historyRow.appendChild(historyCell);
            dataBody.appendChild(historyRow);
            historyButton.addEventListener('click', function() {
                historyRow.hidden = !historyRow.hidden;
                historyButton.textContent = historyRow.hidden ? '🕘 Előzmények' : '✖ Előzmények bezárása';
                if (!historyRow.hidden && !historyContainer.dataset.loaded) {
                    historyContainer.dataset.loaded = 'true';
                    loadItemHistory(historyContainer, currentView, item.sharepoint_item_id, 1);
                }
            });
            if (currentView === 'eszkozleltar_nonIT') {
                var imageCell = document.createElement('td');
                var imageButton = document.createElement('button');
                imageButton.type = 'button';
                imageButton.className = 'btn';
                imageButton.textContent = '🖼️ Képek';
                imageButton.style.cssText = 'white-space:nowrap; padding:5px 8px;';
                imageCell.appendChild(imageButton);
                row.appendChild(imageCell);

                var imageRow = document.createElement('tr');
                imageRow.hidden = true;
                var imageDetailCell = document.createElement('td');
                imageDetailCell.colSpan = columns.length + 2;
                imageDetailCell.style.cssText = 'padding:0; background:#f8fafc;';
                var imageContainer = document.createElement('div');
                imageDetailCell.appendChild(imageContainer);
                imageRow.appendChild(imageDetailCell);
                dataBody.appendChild(imageRow);
                imageButton.addEventListener('click', function() {
                    imageRow.hidden = !imageRow.hidden;
                    imageButton.textContent = imageRow.hidden ? '🖼️ Képek' : '✖ Képek bezárása';
                    if (!imageRow.hidden && !imageContainer.dataset.loaded) {
                        imageContainer.dataset.loaded = 'true';
                        loadImageVersions(imageContainer, item.sharepoint_item_id);
                    }
                });
            }
        });
        appendPagination(total, page, window.loadSharePointData);
    }

    window.showSharePointDataView = function(viewName) {
        if (listNames.indexOf(viewName) === -1 && viewName !== 'changes') return;
        currentView = viewName;
        currentPage = 1;
        document.querySelectorAll('[data-sharepoint-view]').forEach(function(button) {
            button.classList.toggle('active', button.getAttribute('data-sharepoint-view') === viewName);
        });
        var listControls = document.getElementById('sharepoint-data-list-controls');
        var changesControls = document.getElementById('sharepoint-changes-controls');
        if (imageSyncButton) imageSyncButton.hidden = viewName !== 'eszkozleltar_nonIT';
        if (listControls) listControls.style.display = viewName === 'changes' ? 'none' : 'flex';
        if (changesControls) changesControls.style.display = viewName === 'changes' ? 'block' : 'none';
        if (viewName === 'changes') window.loadSharePointChanges();
        else window.loadSharePointData();
    };

    window.loadSharePointData = async function() {
        if (currentView === 'changes') return;
        setTableMessage('Helyi SharePoint-adatok betöltése...', 1);
        var params = new URLSearchParams({
            search: document.getElementById('sharepoint-data-search')?.value || '',
            sort_by: currentSort.startsWith('field:') ? currentSort.slice(6) : currentSort,
            sort_direction: sortDirection,
            page: String(currentPage),
            page_size: String(pageSize),
            show_deleted: String(Boolean(document.getElementById('sharepoint-data-show-deleted')?.checked))
        });
        try {
            var response = await fetch('/api/settings/sharepoint/data/' + encodeURIComponent(currentView) + '?' + params);
            var result = await response.json();
            if (!response.ok || result.status !== 'SUCCESS') {
                throw new Error(result.message || result.detail || 'A helyi adatok betöltése nem sikerült.');
            }
            dataStatus.style.display = 'none';
            renderList(result.items || [], result.total || 0, result.page || 1, result.field_names || []);
            return true;
        } catch (error) {
            setTableMessage('Nem sikerült betölteni a helyi SharePoint-adatokat.', 1);
            showStatus(dataStatus, 'Adatbetöltési hiba: ' + error.message, false);
            return false;
        }
    };

    window.loadSharePointChanges = async function() {
        setTableMessage('Változási előzmények betöltése...', 6);
        var params = new URLSearchParams({
            search: document.getElementById('sharepoint-changes-search')?.value || '',
            page: String(currentPage),
            page_size: String(pageSize)
        });
        try {
            var response = await fetch('/api/settings/sharepoint/changes?' + params);
            var result = await response.json();
            if (!response.ok || result.status !== 'SUCCESS') {
                throw new Error(result.message || result.detail || 'A változások betöltése nem sikerült.');
            }
            renderChanges(result.changes || [], result.total || 0, result.page || 1);
            dataStatus.style.display = 'none';
            return true;
        } catch (error) {
            setTableMessage('Nem sikerült betölteni a SharePoint-változásokat.', 6);
            showStatus(dataStatus, 'Változásbetöltési hiba: ' + error.message, false);
            return false;
        }
    };

    function renderChanges(changes, total, page) {
        var columns = ['Dátum', 'Lista', 'Elem ID', 'Változás', 'Módosult mezők', 'Előtte / utána'];
        dataHead.replaceChildren();
        var header = document.createElement('tr');
        columns.forEach(function(name) {
            var cell = document.createElement('th');
            cell.textContent = name;
            header.appendChild(cell);
        });
        dataHead.appendChild(header);
        dataBody.replaceChildren();
        requestAnimationFrame(updateHorizontalScrollbar);
        if (!changes.length) {
            setTableMessage('Még nincs rögzített SharePoint-változás.', columns.length);
            return;
        }

        changes.forEach(function(change) {
            var row = document.createElement('tr');
            addCell(row, change.changed_at ? new Date(change.changed_at).toLocaleString('hu-HU') : '-');
            addCell(row, listLabels[change.list_name] || change.list_name);
            addCell(row, change.sharepoint_item_id);
            addCell(row, change.change_type);
            addCell(row, (change.changed_fields || []).join(', ') || '-');
            var detailsCell = document.createElement('td');
            var details = document.createElement('details');
            var summary = document.createElement('summary');
            summary.textContent = 'Részletek';
            details.appendChild(summary);
            var before = document.createElement('pre');
            before.textContent = 'Előtte: ' + JSON.stringify(change.previous_fields, null, 2);
            var after = document.createElement('pre');
            after.textContent = 'Utána: ' + JSON.stringify(change.current_fields, null, 2);
            details.appendChild(before);
            details.appendChild(after);
            detailsCell.appendChild(details);
            row.appendChild(detailsCell);
            dataBody.appendChild(row);
        });
        appendPagination(total, page, window.loadSharePointChanges);
    }

    window.searchSharePointData = function() {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function() {
            currentPage = 1;
            window.loadSharePointData();
        }, 250);
    };

    window.searchSharePointChanges = function() {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function() {
            currentPage = 1;
            window.loadSharePointChanges();
        }, 250);
    };

    window.filterSharePointColumns = function() {
        var filter = (document.getElementById('sharepoint-column-search')?.value || '').toLocaleLowerCase('hu-HU');
        document.querySelectorAll('#sharepoint-column-options label').forEach(function(label) {
            label.hidden = !label.dataset.columnLabel.includes(filter);
        });
    };

    window.selectSharePointColumns = function(selectAll) {
        var definitions = getColumnDefinitions(currentFieldNames);
        var selectedColumns = selectAll
            ? definitions
            : definitions.filter(function(column) {
                return baseColumns.some(function(baseColumn) { return baseColumn[0] === column[0]; });
            });
        var selected = new Set(selectedColumns.map(function(column) { return column[0]; }));
        saveVisibleColumns(definitions, selected);
        renderList(currentItems, currentTotal, currentPage, currentFieldNames);
    };

    window.exportSharePointList = async function() {
        if (listNames.indexOf(currentView) === -1) return;
        var button = document.getElementById('btn-export-sharepoint-data');
        if (button) {
            button.disabled = true;
            button.textContent = '⏳ XLSX készítése...';
        }
        try {
            var params = new URLSearchParams({
                show_deleted: String(Boolean(document.getElementById('sharepoint-data-show-deleted')?.checked))
            });
            var response = await fetch('/api/settings/sharepoint/export/' + encodeURIComponent(currentView) + '?' + params);
            if (!response.ok) {
                var error = await response.json();
                throw new Error(error.message || error.detail || 'Az XLSX export nem sikerült.');
            }
            var blob = await response.blob();
            var disposition = response.headers.get('Content-Disposition') || '';
            var filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
            var filename = filenameMatch ? filenameMatch[1] : currentView + '.xlsx';
            var downloadUrl = URL.createObjectURL(blob);
            var link = document.createElement('a');
            link.href = downloadUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(function() { URL.revokeObjectURL(downloadUrl); }, 1000);
            showStatus(dataStatus, 'Az aktuális lista teljes XLSX-exportja elkészült.', true);
        } catch (error) {
            showStatus(dataStatus, 'XLSX export hiba: ' + error.message, false);
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = '⬇️ XLSX export';
            }
        }
    };

    window.syncSharePointData = async function() {
        if (dataRefreshButton) {
            dataRefreshButton.disabled = true;
            dataRefreshButton.textContent = '⏳ Mind a négy lista frissítése...';
        }
        showStatus(dataStatus, 'A négy SharePoint-lista letöltése és változásainak rögzítése folyamatban...', true);
        try {
            var response = await fetch('/api/settings/sharepoint/download-all', { method: 'POST' });
            var result = await response.json();
            if (!response.ok || result.status !== 'SUCCESS') {
                throw new Error(result.message || result.detail || 'A SharePoint-szinkronizálás sikertelen.');
            }
            showStatus(dataStatus, result.message || 'A négy lista frissítése befejeződött.', true);
            currentPage = 1;
            var reloaded = currentView === 'changes'
                ? await window.loadSharePointChanges()
                : await window.loadSharePointData();
            if (!reloaded) return;
            showStatus(dataStatus, result.message || 'A négy lista frissítése befejeződött.', true);
        } catch (error) {
            showStatus(dataStatus, 'SharePoint-szinkronizálási hiba: ' + error.message, false);
        } finally {
            if (dataRefreshButton) {
                dataRefreshButton.disabled = false;
                dataRefreshButton.textContent = '🔄 Mind a négy lista frissítése';
            }
        }
    };

    window.openSharePointImageSyncDialog = function() {
        if (window.location.protocol !== 'https:') {
            showStatus(dataStatus, 'A képszinkron hitelesítési adatokat kér, ezért ezen az oldalon csak HTTPS-en indítható.', false);
            return;
        }
        var dialog = document.getElementById('sharepoint-image-sync-dialog');
        var username = document.getElementById('sharepoint-image-username');
        if (dialog && typeof dialog.showModal === 'function') {
            dialog.showModal();
            if (username) username.focus();
        }
    };

    window.closeSharePointImageSyncDialog = function() {
        var dialog = document.getElementById('sharepoint-image-sync-dialog');
        var form = document.getElementById('sharepoint-image-sync-form');
        if (dialog && dialog.open) dialog.close();
        if (form) form.reset();
    };

    var imageSyncForm = document.getElementById('sharepoint-image-sync-form');
    if (imageSyncForm) {
        var imageSyncDialog = document.getElementById('sharepoint-image-sync-dialog');
        if (imageSyncDialog) {
            imageSyncDialog.addEventListener('close', function() {
                imageSyncForm.reset();
            });
        }
        imageSyncForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            if (window.location.protocol !== 'https:') {
                showStatus(dataStatus, 'A jelszót nem küldtük el: a képszinkron csak HTTPS-en érhető el.', false);
                window.closeSharePointImageSyncDialog();
                return;
            }
            var usernameInput = document.getElementById('sharepoint-image-username');
            var passwordInput = document.getElementById('sharepoint-image-password');
            var submitButton = document.getElementById('btn-submit-sharepoint-image-sync');
            if (!usernameInput || !passwordInput || !submitButton) return;
            var username = usernameInput.value.trim();
            var password = passwordInput.value;
            submitButton.disabled = true;
            submitButton.textContent = '⏳ Képek letöltése...';
            showStatus(dataStatus, 'A képek hitelesített letöltése és verzió-ellenőrzése folyamatban...', true);
            try {
                var response = await fetch('/api/settings/sharepoint/images/sync', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: username, password: password })
                });
                var result = await response.json();
                if (!response.ok) {
                    throw new Error(result.detail || result.message || 'A képszinkron nem sikerült.');
                }
                var summary = result.links_count + ' hivatkozás ellenőrizve; új verzió: ' +
                    result.new_versions_count + ', változatlan: ' + result.unchanged_count +
                    ', kihagyva: ' + result.skipped_count + ', hibás: ' + result.failed_count + '.';
                if (result.error_message) summary += ' ' + result.error_message;
                showStatus(dataStatus, summary, result.status === 'SIKERES');
                if (result.status === 'SIKERES' || result.status === 'RÉSZLEGES') {
                    window.closeSharePointImageSyncDialog();
                    await window.loadSharePointData();
                    showStatus(dataStatus, summary, result.status === 'SIKERES');
                }
            } catch (error) {
                showStatus(dataStatus, 'Képszinkron-hiba: ' + error.message, false);
            } finally {
                passwordInput.value = '';
                submitButton.disabled = false;
                submitButton.textContent = 'Hitelesítés és letöltés';
            }
        });
    }

    window.downloadSharePointLists = async function() {
        var button = document.getElementById('btn-download-sharepoint-lists');
        if (button) {
            button.disabled = true;
            button.textContent = '⏳ Mind a négy lista letöltése...';
        }
        showStatus(statusElement, 'A négy SharePoint-lista letöltése és helyi mentése folyamatban...', true);
        try {
            var response = await fetch('/api/settings/sharepoint/download-all', { method: 'POST' });
            var result = await response.json();
            if (!response.ok || result.status !== 'SUCCESS') {
                throw new Error(result.message || result.detail || 'A SharePoint-szinkronizálás sikertelen.');
            }
            showStatus(statusElement, result.message || 'Mind a négy lista sikeresen letöltve.', true);
        } catch (error) {
            showStatus(statusElement, 'SharePoint-hiba: ' + error.message, false);
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = '⬇️ Mind a négy lista letöltése';
            }
        }
    };

    window.loadSharePointCatalog = async function() {
        if (catalogRefreshButton) {
            catalogRefreshButton.disabled = true;
            catalogRefreshButton.textContent = '⏳ Frissítés...';
        }
        if (catalogBody) {
            catalogBody.replaceChildren();
            var loadingRow = document.createElement('tr');
            var loadingCell = document.createElement('td');
            loadingCell.colSpan = 5;
            loadingCell.textContent = 'SharePoint-listák betöltése...';
            loadingCell.style.textAlign = 'center';
            loadingRow.appendChild(loadingCell);
            catalogBody.appendChild(loadingRow);
        }

        try {
            var response = await fetch('/api/settings/sharepoint/catalog');
            var result = await response.json();
            if (!response.ok || result.status !== 'SUCCESS') {
                throw new Error(result.message || result.detail || 'A SharePoint-listák betöltése nem sikerült.');
            }
            catalogBody.replaceChildren();
            (result.lists || []).forEach(function(list) {
                var row = document.createElement('tr');
                addCell(row, list.display_name);
                addCell(row, list.name);
                addCell(row, list.template);
                addCell(row, list.item_count);
                var action = document.createElement('td');
                action.style.textAlign = 'right';
                action.textContent = list.import_supported ? 'SP_ helyi másolat' : 'Csak megtekintés';
                row.appendChild(action);
                catalogBody.appendChild(row);
            });
            if (!result.lists || !result.lists.length) {
                var emptyRow = document.createElement('tr');
                var emptyCell = document.createElement('td');
                emptyCell.colSpan = 5;
                emptyCell.textContent = 'A SharePoint-webhelyen nem található lista.';
                emptyCell.style.textAlign = 'center';
                emptyRow.appendChild(emptyCell);
                catalogBody.appendChild(emptyRow);
            }
            statusElement.style.display = 'none';
        } catch (error) {
            var errorRow = document.createElement('tr');
            var errorCell = document.createElement('td');
            errorCell.colSpan = 5;
            errorCell.textContent = 'Nem sikerült betölteni a SharePoint-listákat.';
            errorRow.appendChild(errorCell);
            catalogBody.replaceChildren(errorRow);
            showStatus(statusElement, 'SharePoint-hiba: ' + error.message, false);
        } finally {
            if (catalogRefreshButton) {
                catalogRefreshButton.disabled = false;
                catalogRefreshButton.textContent = '🔄 Frissítés';
            }
        }
    };
})();
