-- FPS conversion and time shift made for a subtitle in the admin addon (stored with the
-- subtitle in overrides.json). Whoever downloads the subtitle applies them again:
-- first rescale the timestamps by fps_from / fps_to, then add shift_ms.
--
-- Run once in the Supabase dashboard: SQL Editor > New query > paste > Run.

alter table public.subtitles
    add column if not exists fps_from numeric(7, 3),   -- e.g. 23.976
    add column if not exists fps_to   numeric(7, 3),   -- e.g. 25
    add column if not exists shift_ms integer;         -- + later, - earlier

alter table public.subtitles
    drop constraint if exists subtitles_fps_pair,
    add constraint subtitles_fps_pair check ((fps_from is null) = (fps_to is null)
                                             and coalesce(fps_from, 1) > 0 and coalesce(fps_to, 1) > 0);
