from apps.users.models import User

from ..models import PartyMemberStatus


def ensure_party_profile_for_user(user, created_by=None):
    if not user or user.role not in {User.ROLE_STUDENT, User.ROLE_CADRE}:
        return None

    profile, _ = PartyMemberStatus.objects.get_or_create(
        user=user,
        defaults={
            "track_type": PartyMemberStatus.TrackType.PARTY,
            "current_stage": PartyMemberStatus.Stage.APPLICANT,
            "created_by": created_by,
        },
    )
    if created_by and profile.created_by_id is None:
        profile.created_by = created_by
        profile.save(update_fields=["created_by", "updated_at"])
    return profile
