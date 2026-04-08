local obs = obslua

--------------------------------------------------
-- CONFIG
--------------------------------------------------
local SCORE_FILE_PATH = ""
local LINKS_FILE_PATH = ""

--------------------------------------------------
-- VOICE SOURCES MAPPING
--------------------------------------------------
local VOICE_MAP = {
    WELCOME = "AI_WELCOME",
    DOT = "AI_DOT",
    SINGLE = "AI_SINGLE",
    DOUBLE = "AI_DOUBLE",
    TRIPLE = "AI_TRIPLE",
    FOUR = "AI_FOUR",
    SIX = "AI_SIX",
    WICKET = "AI_WICKET",
    OVER = "AI_OVER",
    WIDE = "AI_WIDE",
    NO_BALL = "AI_NO_BALL",
    FREE_HIT = "AI_FREE_HIT",
    BYE = "AI_BYE",
    LEG_BYE = "AI_LEG_BYE",
    MATCH_END = "AI_MATCH_END",
    TOSS = "AI_TOSS",
    LAST_OVER = "AI_LAST_OVER",
    OVER_COMPLETE = "AI_OVER"
}

--------------------------------------------------
-- INTERNAL STATE
--------------------------------------------------
local last_event = ""
local last_mp3 = ""
local last_crex_url = ""
local last_cricbuzz_url = ""
local last_json_content = ""
local stable_count = 0
local last_size = 0

--------------------------------------------------
-- FLAG SOURCES
--------------------------------------------------
local flag_names = {
    ["Batting Flag"] = true,
    ["Bowling Flag"] = true
}

--------------------------------------------------
-- UTILITY FUNCTIONS
--------------------------------------------------
local function trim(s)
    return (s and s:gsub("^%s+", ""):gsub("%s+$", "")) or ""
end

local function file_exists(filepath)
    if not filepath or filepath == "" then 
        return false 
    end
    local f = io.open(filepath, "r")
    if f then
        f:close()
        return true
    end
    return false
end

local function get_file_size(filepath)
    if not file_exists(filepath) then 
        return 0 
    end
    local f = io.open(filepath, "rb")
    if not f then 
        return 0 
    end
    local size = f:seek("end")
    f:close()
    return size
end

--------------------------------------------------
-- READ AND PARSE JSON SAFELY
--------------------------------------------------
function read_json_safe()
    if SCORE_FILE_PATH == "" then 
        return nil, nil 
    end
    
    if not file_exists(SCORE_FILE_PATH) then 
        return nil, nil 
    end
    
    -- Check if file size is stable
    local current_size = get_file_size(SCORE_FILE_PATH)
    
    if current_size == 0 then
        return nil, nil
    end
    
    -- If size changed, reset stable counter
    if current_size ~= last_size then
        last_size = current_size
        stable_count = 0
        return nil, nil
    end
    
    -- Need 2 consecutive stable reads (1 second with 0.5s timer)
    stable_count = stable_count + 1
    if stable_count < 2 then
        return nil, nil
    end
    
    -- Reset counter after stable
    stable_count = 0
    
    -- Read the file
    local f = io.open(SCORE_FILE_PATH, "r")
    if not f then 
        return nil, nil 
    end
    
    local content = f:read("*all")
    f:close()
    
    if not content or content == "" then 
        return nil, nil 
    end
    
    -- Check if content changed
    if content == last_json_content then
        return nil, nil
    end
    
    -- Try to extract event and MP3
    local event = string.match(content, '"event"%s*:%s*"([^"]+)"')
    if not event then 
        return nil, nil 
    end
    
    -- Get the MP3 file path for this event
    local pattern = '"' .. event .. '"%s*:%s*"([^"]+)"'
    local mp3_file = string.match(content, pattern)
    
    if not mp3_file or mp3_file == "" then 
        return nil, nil 
    end
    
    -- Validate MP3 file exists
    if not file_exists(mp3_file) then
        print("[Cricket] ⏳ MP3 not ready yet: " .. mp3_file)
        return nil, nil
    end
    
    -- Verify file size is reasonable (not empty/corrupt)
    local mp3_size = get_file_size(mp3_file)
    if mp3_size < 500 then
        print("[Cricket] ⚠️ MP3 file too small (" .. mp3_size .. " bytes): " .. mp3_file)
        return nil, nil
    end
    
    -- Store for next comparison
    last_json_content = content
    
    return event, mp3_file
end

--------------------------------------------------
-- PLAY VOICE (SIMPLIFIED WORKING VERSION)
--------------------------------------------------
function play_voice(event_name, mp3_file)
    if not event_name or not mp3_file then
        return false
    end
    
    -- Don't play the same file again
    if mp3_file == last_mp3 then
        print("[Cricket] ⏭️ Skipping duplicate file: " .. mp3_file)
        return false
    end
    
    print("[Cricket] 🎯 Playing event: " .. event_name)
    print("[Cricket] 📁 New MP3 file: " .. mp3_file)
    
    -- Get source name
    local source_name = VOICE_MAP[event_name]
    if not source_name then
        source_name = "AI_" .. event_name
    end
    
    -- Handle OVER_COMPLETE special case
    if event_name == "OVER_COMPLETE" then
        source_name = "AI_OVER"
    end
    
    -- Get media source
    local source = obs.obs_get_source_by_name(source_name)
    if not source then
        print("[Cricket] ❌ Source not found: " .. source_name)
        return false
    end
    
    -- Get current settings
    local settings = obs.obs_source_get_settings(source)
    if not settings then
        print("[Cricket] ❌ Could not get settings for: " .. source_name)
        obs.obs_source_release(source)
        return false
    end
    
    -- Set the file path
    obs.obs_data_set_string(settings, "local_file", mp3_file)
    
    -- Important: Make sure these are set correctly
    obs.obs_data_set_bool(settings, "close_when_inactive", true)
    obs.obs_data_set_bool(settings, "restart_on_activate", true)
    
    -- Update the source
    obs.obs_source_update(source, settings)
    obs.obs_data_release(settings)
    
    -- Stop current playback (if any)
    obs.obs_source_media_stop(source)
    
    -- Small delay using OBS's native sleep
    obs.sleep(10)  -- 10 milliseconds
    
    -- Start playing
    obs.obs_source_media_restart(source)
    
    -- Release the source
    obs.obs_source_release(source)
    
    -- Update last played
    last_mp3 = mp3_file
    last_event = event_name
    
    print("[Cricket] ✅ Play command sent: " .. mp3_file)
    return true
end

--------------------------------------------------
-- URL HELPERS
--------------------------------------------------
local function is_crex_url(u)
    return u and u:match("^https?://[^/]*crex%.com/")
end

local function is_cricbuzz_url(u)
    return u and u:match("^https?://[^/]*cricbuzz%.com/")
end

--------------------------------------------------
-- READ LINKS FILE
--------------------------------------------------
function read_links_file()
    if LINKS_FILE_PATH == "" then 
        return "", "" 
    end
    
    if not file_exists(LINKS_FILE_PATH) then
        return "", ""
    end
    
    local f = io.open(LINKS_FILE_PATH, "r")
    if not f then 
        return "", "" 
    end
    
    local new_crex = ""
    local new_cricbuzz = ""
    
    for line in f:lines() do
        local l = trim(line)
        if new_crex == "" and is_crex_url(l) then
            new_crex = l
        elseif new_cricbuzz == "" and is_cricbuzz_url(l) then
            new_cricbuzz = l
        end
    end
    
    f:close()
    return new_crex, new_cricbuzz
end

--------------------------------------------------
-- UPDATE BROWSER SOURCES
--------------------------------------------------
function apply_links()
    local new_crex, new_cricbuzz = read_links_file()
    
    if new_crex == "" and new_cricbuzz == "" then 
        return 
    end
    
    if new_crex == last_crex_url and new_cricbuzz == last_cricbuzz_url then 
        return 
    end
    
    last_crex_url = new_crex
    last_cricbuzz_url = new_cricbuzz
    
    local sources = obs.obs_enum_sources()
    
    for _, src in ipairs(sources) do
        if obs.obs_source_get_id(src) == "browser_source" then
            local settings = obs.obs_source_get_settings(src)
            if settings then
                local url = obs.obs_data_get_string(settings, "url")
                local name = obs.obs_source_get_name(src)
                
                if is_crex_url(url) then
                    local target = new_crex
                    if flag_names[name] then
                        target = new_crex:gsub("/live$", "/info")
                    end
                    if url ~= target and target ~= "" then
                        obs.obs_data_set_string(settings, "url", target)
                        obs.obs_source_update(src, settings)
                        print("[Cricket] 🔗 Updated Crex URL: " .. name)
                    end
                elseif is_cricbuzz_url(url) then
                    if url ~= new_cricbuzz and new_cricbuzz ~= "" then
                        obs.obs_data_set_string(settings, "url", new_cricbuzz)
                        obs.obs_source_update(src, settings)
                        print("[Cricket] 🔗 Updated Cricbuzz URL: " .. name)
                    end
                end
                
                obs.obs_data_release(settings)
            end
        end
    end
    
    obs.source_list_release(sources)
end

--------------------------------------------------
-- MAIN PROCESS
--------------------------------------------------
function process_score()
    local event, mp3 = read_json_safe()
    
    if event and mp3 then
        -- Only play if this is a new event
        if event ~= last_event then
            play_voice(event, mp3)
        end
    end
end

--------------------------------------------------
-- TIMERS
--------------------------------------------------
function score_timer()
    pcall(process_score)
end

function link_timer()
    pcall(apply_links)
end

--------------------------------------------------
-- OBS UI FUNCTIONS
--------------------------------------------------
function script_description()
    return [[
🏏 Cricket Commentary System - WORKING VERSION

This script reads events from a JSON file and plays corresponding MP3 files.

IMPORTANT SETUP:
1. Create Media Sources named: AI_WELCOME, AI_DOT, AI_SINGLE, AI_DOUBLE, 
   AI_TRIPLE, AI_FOUR, AI_SIX, AI_WICKET, AI_OVER, AI_WIDE, AI_NO_BALL, etc.
2. In each Media Source properties:
   - Set "Local File" (not Input/URL)
   - Check "Close file when inactive" ✓
   - Check "Restart when activated" ✓
3. The JSON file should contain:
   {
       "event": "SINGLE",
       "SINGLE": "C:/cricket_voices/SINGLE_123456.mp3"
   }

TROUBLESHOOTING:
- Make sure the Media Source is visible in your scene
- Check that the Media Source volume is not muted
- Verify the MP3 file plays manually in OBS first
    ]]
end

function script_properties()
    local props = obs.obs_properties_create()
    
    obs.obs_properties_add_path(props, "score_file", "Score JSON File", obs.OBS_PATH_FILE, "*.json", nil)
    obs.obs_properties_add_path(props, "links_file", "Score Links TXT File", obs.OBS_PATH_FILE, "*.txt", nil)
    
    return props
end

function script_update(settings)
    SCORE_FILE_PATH = obs.obs_data_get_string(settings, "score_file")
    LINKS_FILE_PATH = obs.obs_data_get_string(settings, "links_file")
    
    -- Reset state when file path changes
    last_event = ""
    last_mp3 = ""
    last_json_content = ""
    stable_count = 0
    last_size = 0
    
    if SCORE_FILE_PATH ~= "" then
        print("[Cricket] 📄 Score file: " .. SCORE_FILE_PATH)
        -- Test if file exists
        if file_exists(SCORE_FILE_PATH) then
            print("[Cricket] ✅ Score file found")
        else
            print("[Cricket] ❌ Score file NOT found")
        end
    end
    if LINKS_FILE_PATH ~= "" then
        print("[Cricket] 🔗 Links file: " .. LINKS_FILE_PATH)
    end
end

function script_load(settings)
    print("[Cricket] ========================================")
    print("[Cricket] Cricket Commentary System - WORKING")
    print("[Cricket] ========================================")
    
    script_update(settings)
    
    obs.timer_add(score_timer, 500)   -- Check score every 0.5 seconds
    obs.timer_add(link_timer, 5000)   -- Check links every 5 seconds
    
    print("[Cricket] ✅ System ready!")
    print("[Cricket] 💡 Waiting for score updates...")
end

function script_unload()
    print("[Cricket] System unloaded")
    obs.timer_remove(score_timer)
    obs.timer_remove(link_timer)
end