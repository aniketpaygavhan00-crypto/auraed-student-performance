create table if not exists public.student_predictions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    enrollment_no text not null check (char_length(enrollment_no) between 1 and 32),
    study_hours numeric(5, 2) not null check (study_hours between 0 and 24),
    percentage numeric(5, 2) not null check (percentage between 0 and 100),
    attendance numeric(5, 2) not null check (attendance between 0 and 100),
    predicted_percentage integer not null check (predicted_percentage between 0 and 100),
    created_at timestamptz not null default now()
);

create index if not exists student_predictions_user_created_idx
    on public.student_predictions (user_id, created_at desc);

alter table public.student_predictions enable row level security;

drop policy if exists "Students can view their own predictions"
    on public.student_predictions;
create policy "Students can view their own predictions"
    on public.student_predictions
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "Students can insert their own predictions"
    on public.student_predictions;
create policy "Students can insert their own predictions"
    on public.student_predictions
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

grant select, insert on public.student_predictions to authenticated;
