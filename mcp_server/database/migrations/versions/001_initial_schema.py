"""Initial schema creation for Hospital Clinical Intelligence MCP Platform.

Revision ID: 001
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Create patients table
    op.create_table(
        "patients",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.DateTime(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("mrn", sa.String(50), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mrn", name="uq_patient_mrn"),
    )
    op.create_index("idx_patient_mrn", "patients", ["mrn"])
    op.create_index("idx_patient_last_name", "patients", ["last_name"])
    op.create_index("idx_patient_is_active", "patients", ["is_active"])
    op.create_index("idx_patient_created_at", "patients", ["created_at"])

    # Create care_units table
    op.create_table(
        "care_units",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("unit_type", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_care_unit_name"),
        sa.UniqueConstraint("code", name="uq_care_unit_code"),
    )
    op.create_index("idx_care_unit_code", "care_units", ["code"])
    op.create_index("idx_care_unit_is_active", "care_units", ["is_active"])

    # Create encounters table
    op.create_table(
        "encounters",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("care_unit_id", sa.String(36), nullable=False),
        sa.Column("encounter_type", sa.String(50), nullable=False),
        sa.Column("admission_time", sa.DateTime(), nullable=False),
        sa.Column("discharge_time", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("chief_complaint", sa.Text(), nullable=True),
        sa.Column("admission_diagnosis", sa.Text(), nullable=True),
        sa.Column("discharge_diagnosis", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["care_unit_id"], ["care_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_encounter_patient_id", "encounters", ["patient_id"])
    op.create_index("idx_encounter_care_unit_id", "encounters", ["care_unit_id"])
    op.create_index("idx_encounter_admission_time", "encounters", ["admission_time"])
    op.create_index("idx_encounter_is_active", "encounters", ["is_active"])
    op.create_index("idx_encounter_created_at", "encounters", ["created_at"])

    # Create clinicians table
    op.create_table(
        "clinicians",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("specialty", sa.String(100), nullable=True),
        sa.Column("license_number", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_clinician_email"),
    )
    op.create_index("idx_clinician_email", "clinicians", ["email"])
    op.create_index("idx_clinician_role", "clinicians", ["role"])
    op.create_index("idx_clinician_is_active", "clinicians", ["is_active"])

    # Create devices table
    op.create_table(
        "devices",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("device_type", sa.String(100), nullable=False),
        sa.Column("device_name", sa.String(100), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("manufacturer", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("battery_level", sa.Float(), nullable=True),
        sa.Column("calibration_status", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_device_encounter_id", "devices", ["encounter_id"])
    op.create_index("idx_device_type", "devices", ["device_type"])
    op.create_index("idx_device_serial_number", "devices", ["serial_number"])
    op.create_index("idx_device_is_online", "devices", ["is_online"])
    op.create_index("idx_device_is_active", "devices", ["is_active"])

    # Create clinician_care_unit_assignments table
    op.create_table(
        "clinician_care_unit_assignments",
        sa.Column("clinician_id", sa.String(36), nullable=False),
        sa.Column("care_unit_id", sa.String(36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinician_id"], ["clinicians.id"]),
        sa.ForeignKeyConstraint(["care_unit_id"], ["care_units.id"]),
        sa.PrimaryKeyConstraint("clinician_id", "care_unit_id"),
    )

    # Create clinician_assignments table
    op.create_table(
        "clinician_assignments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("clinician_id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinician_id"], ["clinicians.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinician_id", "encounter_id", name="uq_clinician_encounter"),
    )
    op.create_index("idx_clinician_assignment_clinician_id", "clinician_assignments", ["clinician_id"])
    op.create_index("idx_clinician_assignment_encounter_id", "clinician_assignments", ["encounter_id"])
    op.create_index("idx_clinician_assignment_is_active", "clinician_assignments", ["is_active"])

    # Create patient_id_mappings table
    op.create_table(
        "patient_id_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("id_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", "source_system", name="uq_patient_external_id_source"),
    )
    op.create_index("idx_patient_id_mapping_patient_id", "patient_id_mappings", ["patient_id"])
    op.create_index("idx_patient_id_mapping_external_id", "patient_id_mappings", ["external_id"])
    op.create_index("idx_patient_id_mapping_source_system", "patient_id_mappings", ["source_system"])

    # Create encounter_id_mappings table
    op.create_table(
        "encounter_id_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("id_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", "source_system", name="uq_encounter_external_id_source"),
    )
    op.create_index("idx_encounter_id_mapping_encounter_id", "encounter_id_mappings", ["encounter_id"])
    op.create_index("idx_encounter_id_mapping_external_id", "encounter_id_mappings", ["external_id"])
    op.create_index("idx_encounter_id_mapping_source_system", "encounter_id_mappings", ["source_system"])

    # Create care_unit_id_mappings table
    op.create_table(
        "care_unit_id_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("care_unit_id", sa.String(36), nullable=False),
        sa.Column("external_code", sa.String(50), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("code_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["care_unit_id"], ["care_units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_code", "source_system", name="uq_care_unit_external_code_source"),
    )
    op.create_index("idx_care_unit_id_mapping_care_unit_id", "care_unit_id_mappings", ["care_unit_id"])
    op.create_index("idx_care_unit_id_mapping_external_code", "care_unit_id_mappings", ["external_code"])
    op.create_index("idx_care_unit_id_mapping_source_system", "care_unit_id_mappings", ["source_system"])

    # Create device_id_mappings table
    op.create_table(
        "device_id_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("id_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", "source_system", name="uq_device_external_id_source"),
    )
    op.create_index("idx_device_id_mapping_device_id", "device_id_mappings", ["device_id"])
    op.create_index("idx_device_id_mapping_external_id", "device_id_mappings", ["external_id"])
    op.create_index("idx_device_id_mapping_source_system", "device_id_mappings", ["source_system"])

    # Create clinician_id_mappings table
    op.create_table(
        "clinician_id_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("clinician_id", sa.String(36), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("id_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinician_id"], ["clinicians.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", "source_system", name="uq_clinician_external_id_source"),
    )
    op.create_index("idx_clinician_id_mapping_clinician_id", "clinician_id_mappings", ["clinician_id"])
    op.create_index("idx_clinician_id_mapping_external_id", "clinician_id_mappings", ["external_id"])
    op.create_index("idx_clinician_id_mapping_source_system", "clinician_id_mappings", ["source_system"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("clinician_id_mappings")
    op.drop_table("device_id_mappings")
    op.drop_table("care_unit_id_mappings")
    op.drop_table("encounter_id_mappings")
    op.drop_table("patient_id_mappings")
    op.drop_table("clinician_assignments")
    op.drop_table("clinician_care_unit_assignments")
    op.drop_table("devices")
    op.drop_table("clinicians")
    op.drop_table("encounters")
    op.drop_table("care_units")
    op.drop_table("patients")
