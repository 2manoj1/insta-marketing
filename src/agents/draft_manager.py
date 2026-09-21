"""
Human-in-the-Loop (HITL) Email Draft Manager.
Saves individual editable drafts to disk and provides interactive CLI review and editing.
"""
import logging
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from src.config import settings
from src.models.creator import CreatorProfile
from src.models.outreach import OutreachPitch

logger = logging.getLogger(__name__)
console = Console()


class DraftManager:
    """
    Manages cold email and DM drafts with HITL editing and text file exports.
    """

    def save_individual_drafts(
        self,
        username: str,
        pitches: List[OutreachPitch],
    ) -> Path:
        """
        Saves each draft into an individual text file so anyone can open
        and copy-paste it directly into their email client.
        """
        draft_dir = settings.data_dir / "drafts" / username
        draft_dir.mkdir(parents=True, exist_ok=True)

        for p in pitches:
            safe_name = "".join(c for c in p.brand_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            file_path = draft_dir / f"{safe_name}_pitch.txt"

            content = f"""TO: {p.recipient_email}
COMPANY: {p.brand_name}
CREATOR: @{p.creator_username}
STATUS: {p.status.upper()}
SUBJECT: {p.subject_line}
{"=" * 70}
EMAIL BODY:

{p.email_body}

{"=" * 70}
INSTAGRAM DIRECT MESSAGE (DM) ALTERNATIVE:

{p.instagram_dm}

{"=" * 70}
DELIVERABLES PROPOSED:
"""
            for d in p.deliverables:
                content += f"- {d.title}: {d.description} (Usage: {d.usage_rights})\n"

            content += f"\nCALL TO ACTION: {p.call_to_action}\n"

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        console.print(f"[bold green]✓ {len(pitches)} Editable Email Drafts saved to [cyan]{draft_dir}[/cyan][/bold green]")
        return draft_dir

    def hitl_interactive_review(
        self,
        pitches: List[OutreachPitch],
        auto_approve: bool = False,
    ) -> List[OutreachPitch]:
        """
        Human-in-the-Loop review loop.
        Allows the user to view, edit, approve, or reject email drafts interactively.
        Supports:
          [A] Approve All & Save (Default - press Enter)
          [E] Edit a specific draft (Subject, Email, Body)
          [V] View full pitch details
          [R] Reject a draft (Remove from campaign)
          [S] Skip review (Save drafts as-is)
        """
        if auto_approve or not pitches:
            for p in pitches:
                p.status = "approved"
            return pitches

        console.print("\n[bold yellow]══════════ Human-in-the-Loop (HITL) Email Draft Review ══════════[/bold yellow]")
        console.print("[dim]Review, edit, reject, or approve outreach pitches before finalizing.[/dim]\n")

        active_pitches = list(pitches)

        while True:
            # Display current list of active drafts
            for idx, p in enumerate(active_pitches, 1):
                status_color = "green" if p.status == "approved" else "cyan" if p.status == "edited" else "yellow"
                console.print(f"[{idx}] [bold]{p.brand_name}[/bold] -> Recipient: [underline cyan]{p.recipient_email}[/underline cyan] [{status_color}]({p.status.upper()})[/{status_color}]")
                console.print(f"    Subject: \"{p.subject_line}\"")

            console.print("\n[bold white]HITL Actions:[/bold white]")
            console.print("  [bold green][A][/bold green] Approve All & Save (Default - press Enter)")
            console.print("  [bold cyan][E][/bold cyan] Edit a specific draft (Subject, Email, or Body)")
            console.print("  [bold magenta][V][/bold magenta] View full pitch details")
            console.print("  [bold red][R][/bold red] Reject a draft (Remove from campaign)")
            console.print("  [bold yellow][S][/bold yellow] Skip review (Save drafts as-is)")

            action = Prompt.ask(
                "\nSelect action [A/E/V/R/S]",
                choices=["a", "A", "e", "E", "v", "V", "r", "R", "s", "S", ""],
                default="A",
                show_choices=False,
            ).upper() or "A"

            if action in ["A", "S"]:
                for p in active_pitches:
                    if p.status == "draft":
                        p.status = "approved"
                console.print(f"\n[bold green]✓ Finalized {len(active_pitches)} approved drafts for saving.[/bold green]\n")
                break

            elif action == "R":
                if not active_pitches:
                    console.print("[yellow]No drafts left to reject.[/yellow]")
                    continue
                choice = Prompt.ask(f"Enter draft number to reject (1-{len(active_pitches)}) or 'c' to cancel", default="c")
                if choice.lower() not in ["c", "cancel"]:
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(active_pitches):
                            rejected = active_pitches.pop(idx)
                            console.print(f"[red]✗ Rejected and removed draft for {rejected.brand_name}.[/red]\n")
                        else:
                            console.print("[red]Invalid draft number.[/red]")
                    except ValueError:
                        pass

            elif action == "V":
                choice = Prompt.ask(f"Enter draft number to view (1-{len(active_pitches)})", default="1")
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(active_pitches):
                        target = active_pitches[idx]
                        console.print(Panel(
                            f"[bold cyan]To:[/bold cyan] {target.recipient_email}\n"
                            f"[bold cyan]Subject:[/bold cyan] {target.subject_line}\n\n"
                            f"[bold cyan]Email Body:[/bold cyan]\n{target.email_body}\n\n"
                            f"[bold cyan]Instagram DM:[/bold cyan]\n{target.instagram_dm}\n\n"
                            f"[bold cyan]Call to Action:[/bold cyan] {target.call_to_action}",
                            title=f"Draft #{idx+1}: {target.brand_name}",
                            border_style="magenta"
                        ))
                    else:
                        console.print("[red]Invalid draft number.[/red]")
                except ValueError:
                    pass

            elif action == "E":
                choice = Prompt.ask(f"Enter draft number to edit (1-{len(active_pitches)})", default="1")
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(active_pitches):
                        target = active_pitches[idx]
                        console.print(f"\n[cyan]Editing draft for {target.brand_name}:[/cyan]")

                        new_email = Prompt.ask("Recipient Email", default=target.recipient_email)
                        target.recipient_email = new_email

                        new_subject = Prompt.ask("Subject Line", default=target.subject_line)
                        target.subject_line = new_subject

                        console.print(f"\nCurrent Body:\n[dim]{target.email_body}[/dim]\n")
                        edit_body = Confirm.ask("Do you want to replace the email body text?", default=False)
                        if edit_body:
                            new_body = Prompt.ask("Enter new email body (single line or paste text)", default=target.email_body)
                            if new_body.strip():
                                target.email_body = new_body.strip()

                        target.status = "edited"
                        console.print(f"[bold green]✓ Updated draft #{idx+1} for {target.brand_name}.[/bold green]\n")
                    else:
                        console.print("[red]Invalid draft number.[/red]")
                except ValueError:
                    pass

        return active_pitches

    def get_all_drafts(self, creator_username: Optional[str] = None) -> List[dict]:
        """
        Reads and parses saved draft .txt files from disk.
        Allows instant visualization in CLI and Web UI without running agents.
        """
        base_dir = settings.data_dir / "drafts"
        results = []
        if not base_dir.exists():
            return results

        if creator_username:
            clean_name = creator_username.lower().lstrip("@")
            creator_dirs = [base_dir / clean_name]
        else:
            creator_dirs = [d for d in base_dir.iterdir() if d.is_dir()]

        for c_dir in creator_dirs:
            if not c_dir.exists() or not c_dir.is_dir():
                continue
            creator_name = c_dir.name
            for txt_file in sorted(c_dir.glob("*_pitch.txt")):
                try:
                    text = txt_file.read_text(encoding="utf-8")
                    lines = text.splitlines()
                    meta = {}
                    for line in lines[:10]:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            meta[k.strip().upper()] = v.strip()

                    results.append({
                        "filename": txt_file.name,
                        "file_path": str(txt_file),
                        "creator": meta.get("CREATOR", f"@{creator_name}").lstrip("@"),
                        "company_name": meta.get("COMPANY", txt_file.stem.replace("_pitch", "").replace("_", " ")),
                        "recipient_email": meta.get("TO", ""),
                        "subject": meta.get("SUBJECT", ""),
                        "full_content": text,
                    })
                except Exception as e:
                    logger.warning(f"Failed to read draft file {txt_file}: {e}")

        return results


draft_manager = DraftManager()

