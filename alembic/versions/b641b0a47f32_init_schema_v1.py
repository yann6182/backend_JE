"""init schema v1"""
revision = 'b641b0a47f32'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table('clients',
    sa.Column('id_client', sa.Integer(), nullable=False),
    sa.Column('nom_client', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id_client')
    )
    op.create_table('dpgf',
    sa.Column('id_dpgf', sa.Integer(), nullable=False),
    sa.Column('id_client', sa.Integer(), nullable=False),
    sa.Column('nom_projet', sa.String(length=255), nullable=False),
    sa.Column('date_dpgf', sa.Date(), nullable=False),
    sa.Column('statut_offre', sa.Enum('en_cours', 'acceptee', 'refusee', name='statutoffre'), nullable=False),
    sa.Column('fichier_source', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['id_client'], ['clients.id_client'], ),
    sa.PrimaryKeyConstraint('id_dpgf')
    )
    op.create_table('lots',
    sa.Column('id_lot', sa.Integer(), nullable=False),
    sa.Column('id_dpgf', sa.Integer(), nullable=False),
    sa.Column('numero_lot', sa.String(length=50), nullable=False),
    sa.Column('nom_lot', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['id_dpgf'], ['dpgf.id_dpgf'], ),
    sa.PrimaryKeyConstraint('id_lot')
    )
    op.create_table('sections',
    sa.Column('id_section', sa.Integer(), nullable=False),
    sa.Column('id_lot', sa.Integer(), nullable=False),
    sa.Column('section_parent_id', sa.Integer(), nullable=True),
    sa.Column('numero_section', sa.String(length=50), nullable=False),
    sa.Column('titre_section', sa.String(length=255), nullable=False),
    sa.Column('niveau_hierarchique', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['id_lot'], ['lots.id_lot'], ),
    sa.ForeignKeyConstraint(['section_parent_id'], ['sections.id_section'], ),
    sa.PrimaryKeyConstraint('id_section')
    )
    op.create_table('elements_ouvrage',
    sa.Column('id_element', sa.Integer(), nullable=False),
    sa.Column('id_section', sa.Integer(), nullable=False),
    sa.Column('designation_exacte', sa.String(length=255), nullable=False),
    sa.Column('unite', sa.String(length=10), nullable=False),
    sa.Column('quantite', sa.DECIMAL(precision=12, scale=3), nullable=False),
    sa.Column('prix_unitaire_ht', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('prix_total_ht', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('offre_acceptee', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['id_section'], ['sections.id_section'], ),
    sa.PrimaryKeyConstraint('id_element')
    )

def downgrade() -> None:
    op.drop_table('elements_ouvrage')
    op.drop_table('sections')
    op.drop_table('lots')
    op.drop_table('dpgf')
    op.drop_table('clients')
