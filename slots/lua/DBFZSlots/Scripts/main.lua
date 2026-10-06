-- DBFZSlots: 4a fileira de personagens extras na tela de selecao (parte em Lua/UE4SS).
--
-- A parte nativa (plugins/DBFZSlots.asi) ja trata os extras como icones 45.. do exe e traduz
-- para os indices do blueprint (random 45, extras 46..). Aqui criamos esses icones de verdade:
-- cada extra e um BP_SelectIcon (mesmas animacoes dos originais) clonado do icone da 2a fileira
-- que fica exatamente 2 fileiras acima dele, e anexado a SelectIconList/SelectEffList.
local TAG = "[DBFZSlots] "
local src = debug.getinfo(1, "S").source:sub(2):gsub("\\", "/")
local MODDIR = src:match("^(.*)/[Ss]cripts/main%.lua$") or "Mods/DBFZSlots"
local WIN64 = MODDIR:match("^(.*)/ue4ss/[Mm]ods/") or MODDIR:match("^(.*)/[Mm]ods/") or "."
local DLL = WIN64 .. "/plugins/DBFZSlots.asi"
local CFG = WIN64 .. "/plugins/DBFZSlots"

local logfile = io.open(CFG .. "/dbfzslots_lua.log", "w")
local function log(s)
    s = tostring(s)
    print(TAG .. s .. "\n")
    if logfile then logfile:write(os.date("[%H:%M:%S] ") .. s .. "\n"); logfile:flush() end
end

local BP_RANDOM = 45          -- indice do random no blueprint
local ROW_SHIFT = 384         -- 2 fileiras da mascara (128 px) x 3 = unidades do canvas
-- icone-molde (indice 0-based na SelectIconList) de cada slot da 4a fileira, esq -> dir
local TEMPLATES = {34, 30, 24, 10, 2, 11, 12, 41, 43, 14, 6, 15, 20, 25, 31, 35}

local function lib(name)
    local f, e = package.loadlib(DLL, name)
    if not f then log("loadlib " .. name .. " failed: " .. tostring(e)) end
    return f
end
local loadIcons, preload = lib("dbfz_load_icons"), lib("dbfz_preload")
local checkLayout = lib("dbfz_check_layout")

local function readLines(path)
    local t = {}
    local f = io.open(path, "rb")
    if not f then return t end
    for line in f:lines() do
        line = line:gsub("^\239\187\191", ""):gsub("[;#].*$", "")
        if line:match("%S") then t[#t + 1] = line end
    end
    f:close()
    return t
end

local codes, iconPath = {}, {}
for _, l in ipairs(readLines(CFG .. "/chara_mods.txt")) do
    local c = l:match("^%s*(%w%w%w)")
    if c then codes[#codes + 1] = c end
end
for _, l in ipairs(readLines(CFG .. "/icons.txt")) do
    local c, p = l:match("^%s*(%w%w%w)%s+(%S+)")
    if c then iconPath[c] = p end
end
-- grade mais alta (slots.ini [ui] grid_shift, px em 1280x720): a mascara do cursor ja vem
-- deslocada do instalador; aqui sobem os icones. 64 px = 1 fileira = 192 unidades do canvas.
local GRID_SHIFT = 0
do
    local sect
    for _, l in ipairs(readLines(CFG .. "/slots.ini")) do
        local h = l:match("^%s*%[(.-)%]")
        if h then sect = h:lower() end
        local v = l:match("^%s*grid_shift%s*=%s*(-?%d+)")
        if v and sect == "ui" then GRID_SHIFT = tonumber(v) end
    end
end
local CANVAS_SHIFT = GRID_SHIFT * 3
local nativeY0 = nil      -- Y original do 1o icone (numero, nao UObject): evita subir duas vezes

if #codes > #TEMPLATES then log("more extras than 4th-row slots; using " .. #TEMPLATES) end
log("roster extra: " .. table.concat(codes, ", ") .. " | dll: " .. DLL)

local function alive(o)
    local ok, r = pcall(function() return o ~= nil and o:IsValid() end)
    return ok and r
end

local function try(desc, fn)
    local ok, err = pcall(fn)
    if not ok then log("  failed: " .. desc .. ": " .. tostring(err)) end
    return ok
end

local function paramList(obj, fname)
    local out = {}
    pcall(function()
        local f = obj:GetClass():Reflection():GetFunction(fname)
        f:ForEachProperty(function(p) out[#out + 1] = p:GetFName():ToString() .. ":" .. p:GetClass():GetFName():ToString() end)
    end)
    return table.concat(out, ", ")
end

local done = {}

-- Copia a aparencia de um Image (efeito de brilho do icone) sem passar structs como parametro:
-- recurso do pincel (textura ou material), cor (como tabela), opacidade e visibilidade.
local function copyEff(src, dst, verbose)
    local res = nil
    pcall(function() res = src.Brush.ResourceObject end)
    local cls = "?"
    pcall(function() cls = res:GetClass():GetFName():ToString() end)
    if verbose then log("  efeito-molde: recurso " .. (alive(res) and res:GetFullName() or "nenhum") .. " (" .. cls .. ")") end
    if alive(res) then
        if cls:find("Texture") then
            try("Eff textura", function() dst:SetBrushFromTexture(res, false) end)
        else
            try("Eff material", function() dst:SetBrushFromMaterial(res) end)
        end
    end
    -- O brilho fica com alfa 0 e so acende no destaque (animacao do blueprint). Copiar o alfa do
    -- molde no momento errado (cursor em cima dele) deixava um quadrado branco aceso para sempre.
    try("Eff cor", function()
        local c = src.ColorAndOpacity
        dst:SetColorAndOpacity({R = c.R, G = c.G, B = c.B, A = 0.0})
    end)
    try("Eff visibilidade", function() dst:SetVisibility(src:GetVisibility()) end)
end

local function describe(w, label)
    local vis, op = "?", "?"
    pcall(function() vis = w:GetVisibility() end)
    pcall(function() op = w.RenderOpacity end)
    log(string.format("  %s: visibilidade %s, RenderOpacity %s", label, tostring(vis), tostring(op)))
end

-- Arrays deste motor tem 24 bytes; ForEach funciona, indexacao direta voltou nula.
local function toList(arr)
    local t = {}
    arr:ForEach(function(i, e) t[i] = e:get() end)
    return t
end

local function append(arr, obj, what)
    local before = #arr
    local ok, err = pcall(function() arr[before + 1] = obj end)
    local after = #arr
    local last = toList(arr)[after]
    local same = last ~= nil and alive(last) and last:GetAddress() == obj:GetAddress()
    log(string.format("  %s: %d -> %d itens, ultimo %s%s", what, before, after,
        same and "e o novo widget" or "NAO e o novo widget", ok and "" or (" (erro: " .. tostring(err) .. ")")))
    return same
end

-- IMPORTANTE: nunca guardar UObjects entre callbacks/telas. Ao sair da selecao o jogo destroi
-- os widgets; perguntar depois se "ainda sao validos" faz o UE4SS ler memoria liberada (crash
-- dentro do UE4SS.dll). Cada abertura da selecao busca a tela de novo e cria widgets novos.
local serial = 0
local checkedLayout = false

-- Copia ancoras do slot e a translacao do widget (alguns icones do jogo usam ancora propria;
-- sem isso a mesma "posicao" cai em outro ponto da tela). Estruturas campo a campo.
-- Tamanho padrao dos slots (o mais comum entre os moldes). Alguns icones do jogo (Icon07,
-- Icon21) tem o slot de 512x512 com o desenho de 256 no canto: copiado, o clone ficava meio
-- icone deslocado para cima e para a esquerda.
local normalSize = {icone = nil, efeito = nil}
local function modeSize(slots)
    local count, best, bestN = {}, nil, 0
    for _, sl in ipairs(slots) do
        local ok, sz = pcall(function() return sl:GetSize() end)
        if ok and sz then
            local key = string.format("%.0fx%.0f", sz.X, sz.Y)
            count[key] = (count[key] or 0) + 1
            if count[key] > bestN then bestN, best = count[key], {X = sz.X, Y = sz.Y} end
        end
    end
    return best
end

local function copyPlacement(tslot, slot, twidget, widget, what)
    local info = {}
    try(what .. " alinhamento", function()
        local al = tslot:GetAlignment()
        slot:SetAlignment({X = al.X, Y = al.Y})
        local got = slot:GetAlignment()
        info[#info + 1] = string.format("alignment (%.2f,%.2f)->(%.2f,%.2f)", al.X, al.Y, got.X, got.Y)
    end)
    try(what .. " tamanho", function()
        local sz = tslot:GetSize()
        local n = normalSize[what]
        if n and (sz.X ~= n.X or sz.Y ~= n.Y) then
            info[#info + 1] = string.format("(template off standard %.0fx%.0f)", sz.X, sz.Y)
            sz = n
        end
        slot:SetSize({X = sz.X, Y = sz.Y})
        local got = slot:GetSize()
        info[#info + 1] = string.format("size (%.0f,%.0f)->(%.0f,%.0f)", sz.X, sz.Y, got.X, got.Y)
    end)
    try(what .. " pivo", function()
        local pv = twidget.RenderTransformPivot
        widget:SetRenderTransformPivot({X = pv.X, Y = pv.Y})
        info[#info + 1] = string.format("pivot (%.2f,%.2f)", pv.X, pv.Y)
    end)
    try(what .. " escala", function()
        local sc = twidget.RenderTransform.Scale
        if sc.X ~= 1 or sc.Y ~= 1 then widget:SetRenderScale({X = sc.X, Y = sc.Y}) end
        info[#info + 1] = string.format("scale (%.2f,%.2f)", sc.X, sc.Y)
    end)
    try(what .. " ancoras", function()
        local a = tslot:GetAnchors()
        local mn, mx = a.Minimum, a.Maximum
        slot:SetAnchors({Minimum = {X = mn.X, Y = mn.Y}, Maximum = {X = mx.X, Y = mx.Y}})
        info[#info + 1] = string.format("anchors (%.2f,%.2f)-(%.2f,%.2f)", mn.X, mn.Y, mx.X, mx.Y)
    end)
    try(what .. " translacao", function()
        local t = twidget.RenderTransform.Translation
        if t.X ~= 0 or t.Y ~= 0 then widget:SetRenderTranslation({X = t.X, Y = t.Y}) end
        info[#info + 1] = string.format("translation (%.1f,%.1f)", t.X, t.Y)
    end)
    return table.concat(info, " ")
end

local function createExtra(host, k, code, tmpl, tmplEff, imageClass)
    serial = serial + 1
    local tex = iconPath[code] and StaticFindObject(iconPath[code])
    if not alive(tex) then log("  icon texture not found: " .. tostring(iconPath[code])); tex = nil end
    local icon = StaticConstructObject(tmpl:GetClass(), host.WidgetTree, FName(string.format("DBFZExtra_%s_%d", code, serial)))
    if not alive(icon) then log("  could not create the icon"); return nil end
    if tex then try("IconTex", function() icon.IconTex = tex end) end
    local tslot = tmpl.Slot
    local slot = tslot.Parent:AddChildToCanvas(icon)
    local place = copyPlacement(tslot, slot, tmpl, icon, "icone")
    local pos = tslot:GetPosition()
    slot:SetPosition({X = pos.X, Y = pos.Y + ROW_SHIFT})
    -- fileiras de baixo ficam na frente (1a=0, 2a=1, 3a=2): a 4a e a 2a + 2
    slot:SetZOrder(tslot:GetZOrder() + 2)
    log(string.format("  %s: pos (%.1f,%.1f) %s", code, pos.X, pos.Y, place))
    if tex then try("CS_CIcon:SetBrushFromTexture", function() icon.CS_CIcon:SetBrushFromTexture(tex, false) end) end

    local eff = StaticConstructObject(imageClass, host.WidgetTree, FName(string.format("DBFZExtraEff_%s_%d", code, serial)))
    copyEff(tmplEff, eff, k == 1)
    local eslot = tmplEff.Slot
    local es = eslot.Parent:AddChildToCanvas(eff)
    copyPlacement(eslot, es, tmplEff, eff, "efeito")
    local ep = eslot:GetPosition()
    es:SetPosition({X = ep.X, Y = ep.Y + ROW_SHIFT})
    es:SetZOrder(eslot:GetZOrder())
    return {icon = icon, eff = eff}
end

-- Moldes da 4a fileira tirados da propria tela: a fileira de 16 icones (a 2a), esq -> dir.
-- As fileiras sao levemente inclinadas, entao agrupa por saltos grandes de Y. Se algo nao
-- bater, usa a tabela fixa TEMPLATES.
local function rowTemplates(iconList)
    local pts = {}
    for i = 1, BP_RANDOM do
        local ok, pos = pcall(function() return iconList[i].Slot:GetPosition() end)
        if ok and pos then pts[#pts + 1] = {idx = i - 1, x = pos.X, y = pos.Y} end
    end
    if #pts ~= BP_RANDOM then return nil, "positions read: " .. #pts end
    table.sort(pts, function(a, b) return a.y < b.y end)
    local rows, cur = {}, {pts[1]}
    for i = 2, #pts do
        if pts[i].y - pts[i - 1].y > 150 then rows[#rows + 1] = cur; cur = {} end
        cur[#cur + 1] = pts[i]
    end
    rows[#rows + 1] = cur
    local sizes = {}
    for _, r in ipairs(rows) do sizes[#sizes + 1] = #r end
    for _, r in ipairs(rows) do
        if #r == 16 then
            table.sort(r, function(a, b) return a.x < b.x end)
            local t = {}
            for _, q in ipairs(r) do t[#t + 1] = q.idx end
            return t, "rows " .. table.concat(sizes, "/")
        end
    end
    return nil, "no row of 16 (rows " .. table.concat(sizes, "/") .. ")"
end

-- Garante os extras na tela: cria (1a vez) ou reanexa (tela reaberta). Idempotente.
local function ensureExtras(host)
    local icons, effs = host.SelectIconList, host.SelectEffList
    local iconList = toList(icons)
    local n0 = #iconList
    local count = math.min(#codes, #TEMPLATES)
    if n0 == BP_RANDOM + 1 + count then return end              -- ja estao la
    if n0 ~= BP_RANDOM + 1 then
        log("SelectIconList has " .. n0 .. " items (expected " .. (BP_RANDOM + 1) .. "); nothing done")
        return
    end
    local effList = toList(effs)
    log("creating " .. count .. " extras in " .. host:GetFullName())
    if CANVAS_SHIFT ~= 0 then
        local y = iconList[1].Slot:GetPosition().Y
        nativeY0 = nativeY0 or y
        if math.abs(y - nativeY0) < 1 then
            for i = 1, BP_RANDOM + 1 do                      -- 45 icones da grade + random
                for _, w in ipairs({iconList[i], effList[i]}) do
                    try("subir " .. i, function()
                        local sl = w.Slot
                        local q = sl:GetPosition()
                        sl:SetPosition({X = q.X, Y = q.Y - CANVAS_SHIFT})
                    end)
                end
            end
            log("grid moved up " .. GRID_SHIFT .. " px (" .. CANVAS_SHIFT .. " on the canvas)")
        else
            log("grid was already moved")
        end
    end
    if not checkedLayout and checkLayout then checkedLayout = true; pcall(checkLayout) end   -- dbfzslots.log
    if loadIcons then pcall(loadIcons) end
    local imageClass = StaticFindObject("/Script/UMG.Image")
    local templates, why = rowTemplates(iconList)
    if templates then
        log("templates from the screen (" .. why .. "): " .. table.concat(templates, ","))
    else
        templates = TEMPLATES
        log("fixed templates (" .. tostring(why) .. ")")
    end
    local tIcons, tEffs = {}, {}
    for _, ti in ipairs(templates) do
        tIcons[#tIcons + 1] = iconList[ti + 1].Slot
        tEffs[#tEffs + 1] = effList[ti + 1].Slot
    end
    normalSize.icone, normalSize.efeito = modeSize(tIcons), modeSize(tEffs)
    log(string.format("standard size: icon %s, effect %s",
        normalSize.icone and string.format("%.0fx%.0f", normalSize.icone.X, normalSize.icone.Y) or "?",
        normalSize.efeito and string.format("%.0fx%.0f", normalSize.efeito.X, normalSize.efeito.Y) or "?"))
    for k = 1, count do
        local code, ti = codes[k], templates[k]
        log(string.format("extra %d %s: template %s", k, code, iconList[ti + 1]:GetFName():ToString()))
        local w = createExtra(host, k, code, iconList[ti + 1], effList[ti + 1], imageClass)
        if not w then return end
        try("Eff apagado", function() w.eff:SetColorAndOpacity({R = 1.0, G = 1.0, B = 1.0, A = 0.0}) end)
        if not append(icons, w.icon, "SelectIconList") or not append(effs, w.eff, "SelectEffList") then
            log("  could not append to the arrays; the icon stays visible but without the highlight animation")
        end
        try("visivel", function() w.icon:SetVisibility(4) end)
        try("PlayCSSelectIconIn", function() w.icon:PlayCSSelectIconIn() end)
    end
    for k = 1, count do
        local bp = BP_RANDOM + k
        try("SetDispIcon " .. bp, function() host:SetDispIcon(bp, true) end)
        try("SetIconSelectFlag " .. bp, function() host:SetIconSelectFlag(bp, false) end)
    end
end

-- Objetos em destruicao (troca de tela) nao podem ser tocados: filtra pelas flags, como o
-- port Xbox (DBFZSlotsIcons) faz.
local DYING_INTERNAL = 0x30000000   -- Unreachable | PendingKill
local DYING_FLAGS = 0x00018000      -- RF_BeginDestroyed | RF_FinishDestroyed
local function healthy(obj)
    local ok, res = pcall(function()
        return obj:IsValid() and not obj:HasAnyInternalFlags(DYING_INTERNAL) and not obj:HasAnyFlags(DYING_FLAGS)
    end)
    return ok and res
end

local function findHost()
    local list = FindObjects(0, "BP_CharaSelect_IconList_C", nil, 0, DYING_FLAGS | 0x30, false) or {}
    for _, h in ipairs(list) do
        if healthy(h) then
            local full = h:GetFullName()
            if full:find("Transient", 1, true) and not full:find("Default__", 1, true) then return h, full end
        end
    end
end

-- Paineis de assistencia e cor (no BP_CharaSelect_Main) sobem junto com a grade. O Y original
-- de cada um e guardado como numero (por nome), entao reaplicar e idempotente.
local PANELS = {}
for _, side in ipairs({"1P", "2P"}) do
    for i = 1, 3 do
        PANELS[#PANELS + 1] = "AssistSelect" .. side .. "_Chara" .. i
        PANELS[#PANELS + 1] = "ColorSelect" .. side .. "_Chara" .. i
    end
end
local panelY0 = {}
local function shiftPanels()
    if CANVAS_SHIFT == 0 then return end
    local main
    for _, m in ipairs(FindObjects(0, "BP_CharaSelect_Main_C", nil, 0, DYING_FLAGS | 0x30, false) or {}) do
        if healthy(m) and m:GetFullName():find("Transient", 1, true) then main = m; break end
    end
    if not main then log("panels: BP_CharaSelect_Main not found"); return end
    local moved, info = 0, {}
    for _, name in ipairs(PANELS) do
        local ok, err = pcall(function()
            local w = main[name]
            if not w or not w:IsValid() then error("no widget") end
            local sl = w.Slot
            local q = sl:GetPosition()
            panelY0[name] = panelY0[name] or q.Y
            sl:SetPosition({X = q.X, Y = panelY0[name] - CANVAS_SHIFT})
            moved = moved + 1
        end)
        if not ok then info[#info + 1] = name .. ": " .. tostring(err) end
    end
    log("assist/color panels: " .. moved .. "/" .. #PANELS .. " moved up" ..
        (#info > 0 and (" (" .. table.concat(info, "; ") .. ")") or ""))
end

-- (a area de movimento do cursor sobe no plugin nativo: SetCursorMoveArea em slots.c)

-- Gatilho barato: a DLL conta as buscas de retrato da tela de selecao (so acontecem com ela
-- aberta). Quando a tela (re)abre depois de um tempo sem atividade, conferimos os extras;
-- a busca de objetos so acontece se a tela guardada nao existir mais.
local selectSeen = lib("dbfz_select_seen")
local searching = false
local function search(tries)
    ExecuteInGameThread(function()
        local ok, err = pcall(function()
            local host = findHost()
            if not host then
                if tries < 20 then ExecuteWithDelay(250, function() search(tries + 1) end) else searching = false end
                return
            end
            searching = false
            ensureExtras(host)
            pcall(shiftPanels)
        end)
        if not ok then searching = false; log("error: " .. tostring(err)) end
    end)
end
if selectSeen then
    local idle = 100
    LoopAsync(500, function()
        if selectSeen(true) then
            if idle >= 6 and not searching then    -- 3 s sem atividade: tela recem-aberta
                searching = true
                ExecuteWithDelay(300, function() search(0) end)
            end
            idle = 0
        else
            idle = idle + 1
        end
        return false
    end)
else
    log("dbfz_select_seen unavailable; the 4th row will not be created")
end

if preload then
    ExecuteWithDelay(8000, function() ExecuteInGameThread(function() pcall(preload) end) end)
end
log("waiting for the character select screen")
