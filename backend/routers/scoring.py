from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..core.security import check_is_commissioner, get_current_user
from ..database import get_db
from ..schemas.scoring import ScoringRule, ScoringRuleCreate, ScoringTemplate

router = APIRouter(prefix="/scoring", tags=["scoring"])


class ScoringRuleUpdateRequest(BaseModel):
    category: str | None = None
    event_name: str | None = None
    description: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    point_value: float | None = None
    calculation_type: str | None = None
    applicable_positions: list[str] | None = None
    position_ids: list[int] | None = None
    season_year: int | None = None
    source: str | None = None
    is_active: bool | None = None


class ScoringRuleUpsertItem(ScoringRuleCreate):
    id: int | None = None


class ScoringRuleBatchUpsertRequest(BaseModel):
    rules: list[ScoringRuleUpsertItem] = Field(default_factory=list)
    replace_existing_for_season: bool = False
    season_year: int | None = None


class TemplateWithRulesCreateRequest(BaseModel):
    name: str
    description: str | None = None
    season_year: int | None = None
    source_platform: str = "custom"
    is_system_template: bool = False
    rules: list[ScoringRuleCreate] = Field(default_factory=list)


class TemplateApplyRequest(BaseModel):
    season_year: int | None = None
    deactivate_existing: bool = True


class TemplateImportRequest(BaseModel):
    template_name: str
    season_year: int | None = None
    source_platform: str = "imported"
    csv_content: str


class ScoringRuleProposalCreateRequest(BaseModel):
    title: str
    description: str | None = None
    proposed_change: dict[str, Any]
    season_year: int | None = None
    voting_deadline: datetime | None = None


class ScoringRuleVoteRequest(BaseModel):
    vote: str  # yes|no|abstain
    comment: str | None = None
    vote_weight: float = 1.0


class ScoringRuleProposalFinalizeRequest(BaseModel):
    status: str  # approved|rejected|cancelled


class RuleSetResponse(BaseModel):
    league_id: int
    season_year: int | None
    active_rule_count: int
    rules: list[ScoringRule]


def _league_id_or_400(user: models.User) -> int:
    if not user.league_id:
        raise HTTPException(status_code=400, detail="User is not associated with a league")
    return int(user.league_id)


def _append_change_log(
    db: Session,
    *,
    league_id: int,
    scoring_rule_id: int | None,
    season_year: int | None,
    change_type: str,
    changed_by_user_id: int | None,
    rationale: str | None,
    previous_value: dict[str, Any] | None,
    new_value: dict[str, Any] | None,
) -> None:
    db.add(
        models.ScoringRuleChangeLog(
            league_id=league_id,
            scoring_rule_id=scoring_rule_id,
            season_year=season_year,
            change_type=change_type,
            rationale=rationale,
            previous_value=previous_value,
            new_value=new_value,
            changed_by_user_id=changed_by_user_id,
        )
    )


def _rule_to_dict(rule: models.ScoringRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "league_id": rule.league_id,
        "season_year": rule.season_year,
        "category": rule.category,
        "event_name": rule.event_name,
        "description": rule.description,
        "range_min": float(rule.range_min),
        "range_max": float(rule.range_max),
        "point_value": float(rule.point_value),
        "calculation_type": rule.calculation_type,
        "applicable_positions": rule.applicable_positions or [],
        "position_ids": rule.position_ids or [],
        "source": rule.source,
        "is_active": bool(rule.is_active),
        "template_id": rule.template_id,
    }


def _parse_csv_rules(csv_content: str) -> list[ScoringRuleCreate]:
    required_columns = {
        "category",
        "event_name",
        "range_min",
        "range_max",
        "point_value",
        "calculation_type",
        "applicable_positions",
        "position_ids",
    }

    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV content is missing headers")

    missing = required_columns - set(reader.fieldnames)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {sorted(missing)}",
        )

    rules: list[ScoringRuleCreate] = []
    for row in reader:
        rules.append(
            ScoringRuleCreate(
                category=row["category"],
                event_name=row["event_name"],
                description=row.get("description") or None,
                range_min=float(row["range_min"]),
                range_max=float(row["range_max"]),
                point_value=float(row["point_value"]),
                calculation_type=row["calculation_type"] or "flat_bonus",
                applicable_positions=[
                    part.strip() for part in (row.get("applicable_positions") or "").split("|") if part.strip()
                ],
                position_ids=[
                    int(part.strip()) for part in (row.get("position_ids") or "").split("|") if part.strip()
                ],
                source="imported",
            )
        )

    return rules


@router.get("/rules", response_model=list[ScoringRule])
def read_scoring_rules(
    season_year: int | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    league_id = _league_id_or_400(current_user)

    query = db.query(models.ScoringRule).filter(models.ScoringRule.league_id == league_id)
    if season_year is not None:
        query = query.filter(models.ScoringRule.season_year == season_year)
    if not include_inactive:
        query = query.filter(models.ScoringRule.is_active.is_(True))

    return query.order_by(models.ScoringRule.event_name.asc(), models.ScoringRule.id.asc()).all()


@router.get("/rulesets/current", response_model=RuleSetResponse)
def read_current_ruleset(
    season_year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    league_id = _league_id_or_400(current_user)
    effective_year = season_year

    query = db.query(models.ScoringRule).filter(
        models.ScoringRule.league_id == league_id,
        models.ScoringRule.is_active.is_(True),
    )
    if effective_year is not None:
        query = query.filter(models.ScoringRule.season_year == effective_year)

    rules = query.order_by(models.ScoringRule.event_name.asc(), models.ScoringRule.id.asc()).all()

    return RuleSetResponse(
        league_id=league_id,
        season_year=effective_year,
        active_rule_count=len(rules),
        rules=[ScoringRule.model_validate(r) for r in rules],
    )


@router.post("/rules", response_model=ScoringRule)
def create_scoring_rule(
    rule: ScoringRuleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    league_id = _league_id_or_400(current_user)
    payload = rule.model_dump()

    db_rule = models.ScoringRule(
        **payload,
        league_id=league_id,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(db_rule)
    db.flush()

    _append_change_log(
        db,
        league_id=league_id,
        scoring_rule_id=db_rule.id,
        season_year=db_rule.season_year,
        change_type="created",
        changed_by_user_id=current_user.id,
        rationale="Rule created via /scoring/rules",
        previous_value=None,
        new_value=_rule_to_dict(db_rule),
    )

    db.commit()
    db.refresh(db_rule)
    return db_rule


@router.put("/rules/{rule_id}", response_model=ScoringRule)
def update_scoring_rule(
    rule_id: int,
    request: ScoringRuleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    league_id = _league_id_or_400(current_user)

    rule = (
        db.query(models.ScoringRule)
        .filter(
            models.ScoringRule.id == rule_id,
            models.ScoringRule.league_id == league_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    previous = _rule_to_dict(rule)
    updates = request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(rule, key, value)

    rule.updated_by_user_id = current_user.id

    _append_change_log(
        db,
        league_id=league_id,
        scoring_rule_id=rule.id,
        season_year=rule.season_year,
        change_type="updated",
        changed_by_user_id=current_user.id,
        rationale="Rule updated via /scoring/rules/{rule_id}",
        previous_value=previous,
        new_value=_rule_to_dict(rule),
    )

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def deactivate_scoring_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    league_id = _league_id_or_400(current_user)

    rule = (
        db.query(models.ScoringRule)
        .filter(
            models.ScoringRule.id == rule_id,
            models.ScoringRule.league_id == league_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    previous = _rule_to_dict(rule)
    rule.is_active = False
    rule.deactivated_at = datetime.now(timezone.utc)
    rule.updated_by_user_id = current_user.id

    _append_change_log(
        db,
        league_id=league_id,
        scoring_rule_id=rule.id,
        season_year=rule.season_year,
        change_type="deleted",
        changed_by_user_id=current_user.id,
        rationale="Rule deactivated via /scoring/rules/{rule_id}",
        previous_value=previous,
        new_value=_rule_to_dict(rule),
    )

    db.commit()
    return {"ok": True, "id": rule_id}


@router.post("/rules/batch-upsert", response_model=list[ScoringRule])
def batch_upsert_scoring_rules(
    request: ScoringRuleBatchUpsertRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    league_id = _league_id_or_400(current_user)
    if not request.rules:
        raise HTTPException(status_code=400, detail="At least one rule is required")

    season_year = request.season_year
    touched_ids: set[int] = set()
    results: list[models.ScoringRule] = []

    for item in request.rules:
        data = item.model_dump(exclude={"id"})
        if season_year is not None:
            data["season_year"] = season_year

        if item.id:
            rule = (
                db.query(models.ScoringRule)
                .filter(
                    models.ScoringRule.id == item.id,
                    models.ScoringRule.league_id == league_id,
                )
                .first()
            )
            if not rule:
                raise HTTPException(status_code=404, detail=f"Rule {item.id} not found")

            previous = _rule_to_dict(rule)
            for key, value in data.items():
                setattr(rule, key, value)
            rule.updated_by_user_id = current_user.id
            touched_ids.add(rule.id)

            _append_change_log(
                db,
                league_id=league_id,
                scoring_rule_id=rule.id,
                season_year=rule.season_year,
                change_type="updated",
                changed_by_user_id=current_user.id,
                rationale="Rule updated via batch-upsert",
                previous_value=previous,
                new_value=_rule_to_dict(rule),
            )
            results.append(rule)
            continue

        rule = models.ScoringRule(
            **data,
            league_id=league_id,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
        )
        db.add(rule)
        db.flush()
        touched_ids.add(rule.id)

        _append_change_log(
            db,
            league_id=league_id,
            scoring_rule_id=rule.id,
            season_year=rule.season_year,
            change_type="created",
            changed_by_user_id=current_user.id,
            rationale="Rule created via batch-upsert",
            previous_value=None,
            new_value=_rule_to_dict(rule),
        )
        results.append(rule)

    if request.replace_existing_for_season:
        query = db.query(models.ScoringRule).filter(
            models.ScoringRule.league_id == league_id,
            models.ScoringRule.is_active.is_(True),
        )
        if season_year is not None:
            query = query.filter(models.ScoringRule.season_year == season_year)

        stale_rules = [r for r in query.all() if r.id not in touched_ids]
        now = datetime.now(timezone.utc)
        for stale in stale_rules:
            previous = _rule_to_dict(stale)
            stale.is_active = False
            stale.deactivated_at = now
            stale.updated_by_user_id = current_user.id
            _append_change_log(
                db,
                league_id=league_id,
                scoring_rule_id=stale.id,
                season_year=stale.season_year,
                change_type="deleted",
                changed_by_user_id=current_user.id,
                rationale="Rule deactivated by batch-upsert replacement",
                previous_value=previous,
                new_value=_rule_to_dict(stale),
            )

    db.commit()
    for row in results:
        db.refresh(row)
    return results


@router.get("/templates", response_model=list[ScoringTemplate])
def list_scoring_templates(
    season_year: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    league_id = _league_id_or_400(current_user)
    query = db.query(models.ScoringTemplate).filter(models.ScoringTemplate.league_id == league_id)
    if season_year is not None:
        query = query.filter(models.ScoringTemplate.season_year == season_year)
    return query.order_by(models.ScoringTemplate.name.asc(), models.ScoringTemplate.id.asc()).all()


@router.post("/templates", response_model=ScoringTemplate)
def create_scoring_template(
    request: TemplateWithRulesCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    league_id = _league_id_or_400(current_user)

    template = models.ScoringTemplate(
        league_id=league_id,
        season_year=request.season_year,
        name=request.name,
        description=request.description,
        source_platform=request.source_platform,
        is_system_template=request.is_system_template,
        created_by_user_id=current_user.id,
    )
    db.add(template)
    db.flush()

    for idx, rule in enumerate(request.rules):
        payload = rule.model_dump()
        payload.setdefault("season_year", request.season_year)
        payload.setdefault("source", "template")

        row = models.ScoringRule(
            **payload,
            league_id=league_id,
            template_id=template.id,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
        )
        db.add(row)
        db.flush()

        db.add(
            models.ScoringTemplateRule(
                template_id=template.id,
                scoring_rule_id=row.id,
                rule_order=idx,
                included=True,
            )
        )

        _append_change_log(
            db,
            league_id=league_id,
            scoring_rule_id=row.id,
            season_year=row.season_year,
            change_type="template_applied",
            changed_by_user_id=current_user.id,
            rationale=f"Rule added to template {template.name}",
            previous_value=None,
            new_value=_rule_to_dict(row),
        )

    db.commit()
    db.refresh(template)
    return template


@router.post("/templates/import", response_model=ScoringTemplate)
def import_scoring_template_from_csv(
    request: TemplateImportRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    rules = _parse_csv_rules(request.csv_content)
    return create_scoring_template(
        TemplateWithRulesCreateRequest(
            name=request.template_name,
            description=f"Imported from CSV via /scoring/templates/import",
            season_year=request.season_year,
            source_platform=request.source_platform,
            rules=rules,
        ),
        db=db,
        current_user=current_user,
    )


@router.get("/templates/{template_id}/export")
def export_scoring_template_to_csv(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    league_id = _league_id_or_400(current_user)

    template = (
        db.query(models.ScoringTemplate)
        .filter(
            models.ScoringTemplate.id == template_id,
            models.ScoringTemplate.league_id == league_id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    rules = (
        db.query(models.ScoringRule)
        .filter(
            models.ScoringRule.template_id == template_id,
            models.ScoringRule.league_id == league_id,
        )
        .order_by(models.ScoringRule.id.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "category",
            "event_name",
            "description",
            "range_min",
            "range_max",
            "point_value",
            "calculation_type",
            "applicable_positions",
            "position_ids",
            "season_year",
            "source",
        ],
    )
    writer.writeheader()
    for rule in rules:
        writer.writerow(
            {
                "category": rule.category,
                "event_name": rule.event_name,
                "description": rule.description or "",
                "range_min": float(rule.range_min),
                "range_max": float(rule.range_max),
                "point_value": float(rule.point_value),
                "calculation_type": rule.calculation_type,
                "applicable_positions": "|".join(rule.applicable_positions or []),
                "position_ids": "|".join(str(x) for x in (rule.position_ids or [])),
                "season_year": rule.season_year or "",
                "source": rule.source,
            }
        )

    return {
        "template_id": template.id,
        "template_name": template.name,
        "filename": f"scoring_template_{template.id}.csv",
        "csv": output.getvalue(),
    }


@router.post("/templates/{template_id}/apply", response_model=list[ScoringRule])
def apply_template_to_active_ruleset(
    template_id: int,
    request: TemplateApplyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    league_id = _league_id_or_400(current_user)

    template = (
        db.query(models.ScoringTemplate)
        .filter(
            models.ScoringTemplate.id == template_id,
            models.ScoringTemplate.league_id == league_id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template_rules = (
        db.query(models.ScoringRule)
        .filter(
            models.ScoringRule.template_id == template_id,
            models.ScoringRule.league_id == league_id,
            models.ScoringRule.is_active.is_(True),
        )
        .order_by(models.ScoringRule.id.asc())
        .all()
    )
    if not template_rules:
        raise HTTPException(status_code=400, detail="Template has no active rules")

    effective_year = request.season_year if request.season_year is not None else template.season_year

    if request.deactivate_existing:
        existing_query = db.query(models.ScoringRule).filter(
            models.ScoringRule.league_id == league_id,
            models.ScoringRule.is_active.is_(True),
            models.ScoringRule.template_id.is_(None),
        )
        if effective_year is not None:
            existing_query = existing_query.filter(models.ScoringRule.season_year == effective_year)

        for row in existing_query.all():
            previous = _rule_to_dict(row)
            row.is_active = False
            row.deactivated_at = datetime.now(timezone.utc)
            row.updated_by_user_id = current_user.id
            _append_change_log(
                db,
                league_id=league_id,
                scoring_rule_id=row.id,
                season_year=row.season_year,
                change_type="deleted",
                changed_by_user_id=current_user.id,
                rationale=f"Rule deactivated before applying template {template.name}",
                previous_value=previous,
                new_value=_rule_to_dict(row),
            )

    created_rules: list[models.ScoringRule] = []
    for src in template_rules:
        row = models.ScoringRule(
            league_id=league_id,
            season_year=effective_year,
            category=src.category,
            event_name=src.event_name,
            description=src.description,
            range_min=src.range_min,
            range_max=src.range_max,
            point_value=src.point_value,
            calculation_type=src.calculation_type,
            applicable_positions=src.applicable_positions,
            position_ids=src.position_ids,
            source="template",
            template_id=template.id,
            created_by_user_id=current_user.id,
            updated_by_user_id=current_user.id,
            is_active=True,
        )
        db.add(row)
        db.flush()

        _append_change_log(
            db,
            league_id=league_id,
            scoring_rule_id=row.id,
            season_year=row.season_year,
            change_type="template_applied",
            changed_by_user_id=current_user.id,
            rationale=f"Template {template.name} applied",
            previous_value=None,
            new_value=_rule_to_dict(row),
        )
        created_rules.append(row)

    db.commit()
    for row in created_rules:
        db.refresh(row)
    return created_rules


@router.post("/proposals")
def create_scoring_rule_proposal(
    request: ScoringRuleProposalCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    league_id = _league_id_or_400(current_user)

    proposal = models.ScoringRuleProposal(
        league_id=league_id,
        season_year=request.season_year,
        title=request.title,
        description=request.description,
        proposed_change=request.proposed_change,
        status="open",
        proposed_by_user_id=current_user.id,
        voting_deadline=request.voting_deadline,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    return {"id": proposal.id, "status": proposal.status}


@router.get("/proposals")
def list_scoring_rule_proposals(
    season_year: int | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    league_id = _league_id_or_400(current_user)

    query = db.query(models.ScoringRuleProposal).filter(models.ScoringRuleProposal.league_id == league_id)
    if season_year is not None:
        query = query.filter(models.ScoringRuleProposal.season_year == season_year)
    if status:
        query = query.filter(models.ScoringRuleProposal.status == status)

    rows = query.order_by(models.ScoringRuleProposal.created_at.desc(), models.ScoringRuleProposal.id.desc()).all()
    return [
        {
            "id": row.id,
            "season_year": row.season_year,
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "voting_deadline": row.voting_deadline,
            "created_at": row.created_at,
            "proposed_by_user_id": row.proposed_by_user_id,
            "vote_count": len(row.votes),
        }
        for row in rows
    ]


@router.post("/proposals/{proposal_id}/vote")
def vote_on_scoring_rule_proposal(
    proposal_id: int,
    request: ScoringRuleVoteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    league_id = _league_id_or_400(current_user)

    proposal = (
        db.query(models.ScoringRuleProposal)
        .filter(
            models.ScoringRuleProposal.id == proposal_id,
            models.ScoringRuleProposal.league_id == league_id,
        )
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.status != "open":
        raise HTTPException(status_code=400, detail="Proposal is not open for voting")

    vote_value = request.vote.lower().strip()
    if vote_value not in {"yes", "no", "abstain"}:
        raise HTTPException(status_code=400, detail="vote must be yes, no, or abstain")

    vote = (
        db.query(models.ScoringRuleVote)
        .filter(
            models.ScoringRuleVote.proposal_id == proposal_id,
            models.ScoringRuleVote.voter_user_id == current_user.id,
        )
        .first()
    )

    if vote:
        vote.vote = vote_value
        vote.comment = request.comment
        vote.vote_weight = request.vote_weight
        vote.voted_at = datetime.now(timezone.utc)
    else:
        vote = models.ScoringRuleVote(
            proposal_id=proposal_id,
            voter_user_id=current_user.id,
            vote=vote_value,
            comment=request.comment,
            vote_weight=request.vote_weight,
        )
        db.add(vote)

    db.commit()

    return {"proposal_id": proposal_id, "voter_user_id": current_user.id, "vote": vote_value}


@router.post("/proposals/{proposal_id}/finalize")
def finalize_scoring_rule_proposal(
    proposal_id: int,
    request: ScoringRuleProposalFinalizeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_is_commissioner),
):
    league_id = _league_id_or_400(current_user)

    proposal = (
        db.query(models.ScoringRuleProposal)
        .filter(
            models.ScoringRuleProposal.id == proposal_id,
            models.ScoringRuleProposal.league_id == league_id,
        )
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    normalized_status = request.status.lower().strip()
    if normalized_status not in {"approved", "rejected", "cancelled"}:
        raise HTTPException(status_code=400, detail="status must be approved, rejected, or cancelled")

    proposal.status = normalized_status
    proposal.finalized_by_user_id = current_user.id
    proposal.finalized_at = datetime.now(timezone.utc)

    db.commit()

    return {"id": proposal.id, "status": proposal.status}


@router.get("/history")
def get_scoring_rule_history(
    season_year: int | None = Query(default=None),
    rule_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    league_id = _league_id_or_400(current_user)

    query = db.query(models.ScoringRuleChangeLog).filter(models.ScoringRuleChangeLog.league_id == league_id)
    if season_year is not None:
        query = query.filter(models.ScoringRuleChangeLog.season_year == season_year)
    if rule_id is not None:
        query = query.filter(models.ScoringRuleChangeLog.scoring_rule_id == rule_id)

    rows = (
        query.order_by(models.ScoringRuleChangeLog.changed_at.desc(), models.ScoringRuleChangeLog.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "scoring_rule_id": row.scoring_rule_id,
            "season_year": row.season_year,
            "change_type": row.change_type,
            "rationale": row.rationale,
            "previous_value": row.previous_value,
            "new_value": row.new_value,
            "changed_by_user_id": row.changed_by_user_id,
            "changed_at": row.changed_at,
        }
        for row in rows
    ]
