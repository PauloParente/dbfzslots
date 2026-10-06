-- DBFZSlotsInspect: ferramenta de debug, somente leitura.
--   F7 = grava em Mods/DBFZSlotsInspect/dump_vs.txt o retrato (CharaTexture) de cada BP_VSChara
--        da tela de VS/carregamento: widget, slot, e todos os parametros do material dinamico
--        (textura, escalares, vetores), que e onde ficam enquadramento e espelhamento.
local TAG = "[DBFZSlotsInspect] "
local function log(s) print(TAG .. tostring(s) .. "\n") end
local src = debug.getinfo(1, "S").source:sub(2):gsub("\\", "/")
local DIR = src:match("^(.*)/[Ss]cripts/main%.lua$") or "Mods/DBFZSlotsInspect"
local OUT = DIR .. "/dump_vs.txt"

local function safe(fn) local ok, r = pcall(fn); if ok then return r end; return nil end
local function vec(v) return v and safe(function() return string.format("(%.2f, %.2f)", v.X, v.Y) end) or "?" end
local DYING_INTERNAL, DYING_FLAGS = 0x30000000, 0x00018000
local function healthy(o)
    local ok, r = pcall(function() return o:IsValid() and not o:HasAnyInternalFlags(DYING_INTERNAL) and not o:HasAnyFlags(DYING_FLAGS) end)
    return ok and r
end

local function pname(e)
    return safe(function() return e.ParameterName:ToString() end)
        or safe(function() return e.ParameterInfo.Name:ToString() end) or "?"
end

local function dumpMID(mid, out)
    out[#out + 1] = "   material: " .. (safe(function() return mid:GetFullName() end) or "?")
    out[#out + 1] = "   pai: " .. (safe(function() return mid.Parent:GetFullName() end) or "?")
    safe(function()
        mid.TextureParameterValues:ForEach(function(i, e)
            local v = e:get()
            out[#out + 1] = string.format("   textura %s = %s", pname(v), safe(function() return v.ParameterValue:GetFullName() end) or "nil")
        end)
    end)
    safe(function()
        mid.ScalarParameterValues:ForEach(function(i, e)
            local v = e:get()
            out[#out + 1] = string.format("   escalar %s = %s", pname(v), tostring(safe(function() return v.ParameterValue end)))
        end)
    end)
    safe(function()
        mid.VectorParameterValues:ForEach(function(i, e)
            local v = e:get()
            local c = safe(function() return v.ParameterValue end)
            out[#out + 1] = string.format("   vetor %s = %s", pname(v),
                c and (safe(function() return string.format("(%.3f, %.3f, %.3f, %.3f)", c.R, c.G, c.B, c.A) end) or "?") or "nil")
        end)
    end)
end

local function dumpVS()
    local out = {"", "######## F7 " .. os.date("%H:%M:%S")}
    local n = 0
    for _, img in ipairs(FindObjects(0, "Image", nil, 0, DYING_FLAGS | 0x30, false) or {}) do
        if healthy(img) then
            local full = safe(function() return img:GetFullName() end) or ""
            if full:find("BP_VSChara", 1, true) and full:find("CharaTexture", 1, true) and full:find("Transient", 1, true) then
                n = n + 1
                out[#out + 1] = "== " .. full
                out[#out + 1] = "   visibilidade " .. tostring(safe(function() return img:GetVisibility() end)) ..
                    " escala render " .. vec(safe(function() return img.RenderTransform.Scale end)) ..
                    " translacao " .. vec(safe(function() return img.RenderTransform.Translation end))
                local slot = safe(function() return img.Slot end)
                if slot then
                    out[#out + 1] = "   slot pos " .. vec(safe(function() return slot:GetPosition() end)) ..
                        " tam " .. vec(safe(function() return slot:GetSize() end))
                end
                local res = safe(function() return img.Brush.ResourceObject end)
                if res and healthy(res) then dumpMID(res, out) end
                -- o widget dono (lado/membro)
                local owner = full:match("(BP_VSChara[%w_]+)")
                out[#out + 1] = "   dono: " .. tostring(owner)
            end
        end
    end
    out[#out + 1] = "-- " .. n .. " retratos da tela de VS"
    local f = io.open(OUT, "a")
    if f then f:write(table.concat(out, "\n"), "\n"); f:close() end
    log("F7: " .. n .. " retratos gravados em " .. OUT)
end

RegisterKeyBind(Key.F7, function()
    ExecuteInGameThread(function()
        local ok, err = pcall(dumpVS)
        if not ok then log("erro: " .. tostring(err)) end
    end)
end)
log("pronto: aperte F7 na tela de VS para gravar os retratos (dump_vs.txt)")
