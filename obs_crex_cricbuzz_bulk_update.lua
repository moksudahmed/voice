-- obs_crex_cricbuzz_bulk_update.lua
-- Replace all crex.com and cricbuzz.com URLs in Browser Sources
-- using a single text file (score_links.txt) that contains the LIVE URL(s).
-- OTHER OVERLAYS use /live
-- FLAG SOURCES (Batting Flag, Bowling Flag) use /info (auto-converted from /live)
-- Also auto-updates when score_links.txt changes.

local obs = obslua
local LINKS_FILE_PATH = ""

-- last seen URLs (for auto-watch)
local last_crex_url = ""
local last_cricbuzz_url = ""

-- কোন কোন সোর্সকে FLAG হিসেবে ধরব
local flag_names = {
    ["Batting Flag"] = true,
    ["Bowling Flag"] = true,
    -- চাইলে এখানে আরও flag source name যোগ করতে পারো
}

function script_description()
    return "Bulk replace crex.com and cricbuzz.com URLs from a single text file.\n" ..
           "Normal overlays use /live, flag overlays use /info.\n" ..
           "Auto-updates when the text file changes."
end

function script_properties()
    local p = obs.obs_properties_create()

    obs.obs_properties_add_path(
        p,
        "links_path",
        "Path to score_links.txt (contains CREX + Cricbuzz LIVE URLs)",
        obs.OBS_PATH_FILE,
        "Text files (*.txt);;All files (*.*)",
        nil
    )

    obs.obs_properties_add_button(p, "apply_btn", "Apply Now", apply_clicked)
    return p
end

function script_update(settings)
    LINKS_FILE_PATH = obs.obs_data_get_string(settings, "links_path")
end

local function trim(s)
    return (s and s:gsub("^%s+", ""):gsub("%s+$", "")) or ""
end

-- Normalize backslashes to forward slashes first, then take directory
local function script_dir()
    local info = debug.getinfo(1, "S")
    local src  = info and info.source or ""
    local path = src:gsub("^@", "")
    path = path:gsub("\\", "/")
    return (path:match("^(.*%/)") or "")
end

local function get_links_file()
    if LINKS_FILE_PATH ~= "" then
        return LINKS_FILE_PATH
    end
    -- default: same folder as this script
    return script_dir() .. "score_links.txt"
end

local function is_crex_url(u)
    if not u or u == "" then return false end
    return u:match("^https?://[^/]*crex%.com/") ~= nil
end

local function is_cricbuzz_url(u)
    if not u or u == "" then return false end
    return u:match("^https?://[^/]*cricbuzz%.com/") ~= nil
end

-- একটাই ফাইল থেকে CREX + Cricbuzz দুটো URL বের করা
local function read_links_file()
    local path = get_links_file()
    local f = io.open(path, "r")
    if not f then
        return "", ""
    end

    local new_crex = ""
    local new_cricbuzz = ""

    for line in f:lines() do
        local l = trim(line)
        if l ~= "" then
            if new_crex == "" and is_crex_url(l) then
                new_crex = l
            elseif new_cricbuzz == "" and is_cricbuzz_url(l) then
                new_cricbuzz = l
            end
        end
        if new_crex ~= "" and new_cricbuzz ~= "" then
            break
        end
    end

    f:close()
    return new_crex, new_cricbuzz
end

local function make_crex_info_url(live_url)
    if not live_url or live_url == "" then
        return ""
    end
    -- সাধারণ কেস: URL-এর শেষে /live থাকলে /info করে দেই
    local info_url = live_url:gsub("/live$", "/info")
    return info_url
end

local function apply_all()
    local new_crex_live, new_cricbuzz = read_links_file()

    -- invalid থাকলে ignore
    if new_crex_live ~= "" and not is_crex_url(new_crex_live) then
        obs.script_log(obs.LOG_WARNING,
            "[crex+cricbuzz-bulk] CREX URL in score_links.txt is not crex.com domain. Skipping CREX updates.")
        new_crex_live = ""
    end

    if new_cricbuzz ~= "" and not is_cricbuzz_url(new_cricbuzz) then
        obs.script_log(obs.LOG_WARNING,
            "[crex+cricbuzz-bulk] Cricbuzz URL in score_links.txt is not cricbuzz.com domain. Skipping Cricbuzz updates.")
        new_cricbuzz = ""
    end

    if new_crex_live == "" and new_cricbuzz == "" then
        obs.script_log(obs.LOG_DEBUG,
            "[crex+cricbuzz-bulk] No valid CREX or Cricbuzz URLs found in score_links.txt. Nothing to update.")
        return
    end

    -- Flag-এর জন্য বিশেষ /info URL
    local new_crex_info = ""
    if new_crex_live ~= "" then
        new_crex_info = make_crex_info_url(new_crex_live)
        if new_crex_info == new_crex_live then
            -- /live পাওয়া যায়নি, তবে ইচ্ছা করলে এখানে warning দিতে পারো
            obs.script_log(obs.LOG_DEBUG,
                "[crex+cricbuzz-bulk] CREX LIVE URL does not end with /live, info URL may be same.")
        end
    end

    local sources = obs.obs_enum_sources()
    if not sources then return end

    local total = 0
    local changed_crex = 0
    local changed_cricbuzz = 0

    for _, src in ipairs(sources) do
        if obs.obs_source_get_id(src) == "browser_source" then
            local s    = obs.obs_source_get_settings(src)
            local cur  = trim(obs.obs_data_get_string(s, "url"))
            local name = obs.obs_source_get_name(src)
            total = total + 1

            -- CREX sources
            if new_crex_live ~= "" and is_crex_url(cur) then
                -- Flag হলে /info, না হলে /live
                local target_url = new_crex_live
                if flag_names[name] and new_crex_info ~= "" then
                    target_url = new_crex_info
                end

                if cur ~= target_url then
                    obs.obs_data_set_string(s, "url", target_url)
                    obs.obs_source_update(src, s)
                    changed_crex = changed_crex + 1
                    obs.script_log(
                        obs.LOG_INFO,
                        string.format("[crex+cricbuzz-bulk] CREX updated (%s): %s", flag_names[name] and "FLAG:/info" or "/live", name)
                    )
                end

            -- Cricbuzz sources
            elseif new_cricbuzz ~= "" and is_cricbuzz_url(cur) then
                local target_url = new_cricbuzz
                if cur ~= target_url then
                    obs.obs_data_set_string(s, "url", target_url)
                    obs.obs_source_update(src, s)
                    changed_cricbuzz = changed_cricbuzz + 1
                    obs.script_log(
                        obs.LOG_INFO,
                        "[crex+cricbuzz-bulk] Cricbuzz updated: " .. name
                    )
                end
            end

            obs.obs_data_release(s)
        end
    end

    obs.source_list_release(sources)

    obs.script_log(
        obs.LOG_INFO,
        string.format(
            "✅ [crex+cricbuzz-bulk] Done. Browser sources: %d | CREX changed: %d | Cricbuzz changed: %d",
            total, changed_crex, changed_cricbuzz
        )
    )
end

-- Timer callback: check if the text file changed (by URLs)
local function check_file_timer()
    local current_crex, current_cricbuzz = read_links_file()

    if current_crex == last_crex_url and current_cricbuzz == last_cricbuzz_url then
        return
    end

    last_crex_url     = current_crex
    last_cricbuzz_url = current_cricbuzz

    obs.script_log(obs.LOG_DEBUG, "[crex+cricbuzz-bulk] Detected change in score_links.txt. Applying...")
    apply_all()
end

function script_load(settings)
    -- শুরুতেই last_* সেট করে একবার আপডেট করি
    last_crex_url, last_cricbuzz_url = read_links_file()
    apply_all()

    -- প্রতি ২ সেকেন্ড পরপর ফাইল চেক
    obs.timer_add(check_file_timer, 2000)
end

function script_unload()
    obs.timer_remove(check_file_timer)
end

function apply_clicked(props, p)
    -- চাইলে এখনও ম্যানুয়ালি Apply Now ব্যবহার করা যাবে
    last_crex_url, last_cricbuzz_url = read_links_file()
    apply_all()
    return true
end
