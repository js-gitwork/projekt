from projektstyring.backend.team_loader import load_teams


teams = load_teams("projektstyring/data/teams.json")

for team in teams.values():
    print(
        team.id,
        team.name,
        team.role,
        team.calendar_id,
        team.capacity_per_day,
        team.task_types,
    )
