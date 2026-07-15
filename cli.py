import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from api_client import APIClient
from ai_service import AIService
from config import clear_token

app = typer.Typer(
    help="🏋️ Workout Tracker CLI — Log workouts, view history, and get AI coaching advice!"
)
console = Console()
api = APIClient()

@app.command()
def register(
        email: str = typer.Option(..., "--email", "-e", prompt=True),
        password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
):
    try:
        api.register(email, password)
        console.print("[bold green]✓ Account registered successfully![/bold green] You can now log in.")
    except Exception as err:
        console.print(f"[bold red]❌ Registration failed:[/bold red] {err}")

@app.command()
def login(
        email: str = typer.Option(..., "--email", "-e", prompt=True),
        password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
):
    try:
        success = api.login(email, password)
        if success:
            console.print("[bold green]✓ Logged in successfully![/bold green] Token stored.")
        else:
            console.print("[bold red]❌ Login failed.[/bold red] Please check your credentials.")
    except Exception as err:
        console.print(f"[bold red]❌ Login error:[/bold red] {err}")

@app.command()
def logout():
    clear_token()
    console.print("[yellow]Logged out successfully.[/yellow]")

@app.command()
def exercises():
    try:
        exercise_list = api.get_exercises()
        if not exercise_list:
            console.print("[yellow]No exercises found in database.[/yellow]")
            return
        
        table = Table(title="Available Exercises", header_style="bold cyan")
        table.add_column("ID", justify="center", style="dim")
        table.add_column("Name", style="bold green")
        table.add_column("Category", style="magenta")
        
        for item in exercise_list:
            table.add_row(
                str(item.get("id")),
                item.get("name", "N/A"),
                item.get("category", "General")
            )
        
        console.print(table)
    except Exception as err:
        console.print(f"[bold red]❌ Error fetching exercises:[/bold red] {err}")


@app.command()
def history():
    try:
        workouts = api.get_workouts()
        if not workouts:
            console.print("[yellow]No logged workouts found.[/yellow]")
            return
        
        table = Table(title="Workout History", header_style="bold magenta")
        table.add_column("ID", justify="center", style="dim")
        table.add_column("Workout Name", style="bold white")
        table.add_column("Logged Date", style="cyan")
        
        for w in workouts:
            table.add_row(
                str(w.get("id")),
                w.get("name", "Untitled Workout"),
                str(w.get("created_at", "N/A"))
            )
        
        console.print(table)
    except Exception as err:
        console.print(f"[bold red]❌ Error loading history:[/bold red] {err}")

@app.command()
def log(
        notes: str = typer.Argument(..., help="Natural language notes of your workout session")
):
    try:
        console.print("[bold cyan]🤖 Fetching exercise list & analyzing notes with Gemini...[/bold cyan]")
        
        available_exercises = api.get_exercises()
        if not available_exercises:
            console.print("[bold red]❌ Cannot parse notes: No exercises found in database.[/bold red]")
            return
        
        ai = AIService()
        parsed = ai.parse_workout_text(notes, available_exercises)
        
        workout_name = parsed.get("workout_name", "AI Parsed Workout")
        sets = parsed.get("sets", [])
        
        if not sets:
            console.print("[bold yellow]⚠️ No exercise sets were parsed from your notes.[/bold yellow]")
            return
        
        # 3. Create workout record
        created_workout = api.create_workout(name=workout_name)
        workout_id = created_workout["id"]
        
        # 4. Log each set
        for s in sets:
            api.add_set(
                workout_id=workout_id,
                exercise_id=s["exercise_id"],
                reps=s["reps"],
                weight=s["weight"],
                set_order=s["set_order"]
            )
        
        console.print(Panel(
            f"[bold green]✓ Successfully logged '{workout_name}'![/bold green]\n"
            f"Logged {len(sets)} sets to Workout ID [bold cyan]#{workout_id}[/bold cyan].",
            title="Workout Saved",
            border_style="green"
        ))
    
    except Exception as err:
        console.print(f"[bold red]❌ AI Logging failed:[/bold red] {err}")

@app.command()
def coach():
    try:
        console.print("[bold cyan]🧠 Analyzing workout history with Gemini...[/bold cyan]")
        workout_history = api.get_workouts()
        
        if not workout_history:
            console.print("[yellow]Log some workouts first so the AI coach has history to review![/yellow]")
            return
        
        ai = AIService()
        advice = ai.get_coaching_advice(workout_history)
        
        console.print(Panel(advice, title="🏋️ AI Fitness Coach Advice", border_style="cyan"))
    except Exception as err:
        console.print(f"[bold red]❌ Coaching request failed:[/bold red] {err}")

if __name__ == "__main__":
    app()