"""
DOCX document generation service for creating montage tables.
Generates documents following Госфильмфонд requirements.
"""

import asyncio
import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import os

from docx import Document
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.shared import OxmlElement, qn
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
from docx.enum.section import WD_SECTION

from app.schemas.film_project import MontageRow, FilmMetadata, ProjectSettings

logger = logging.getLogger(__name__)


class DOCXGenerationError(Exception):
    """Raised when DOCX generation fails."""
    pass


class DOCXTemplateService:
    """Service for managing DOCX templates and formatting."""
    
    # Standard column widths for montage table (in cm)
    COLUMN_WIDTHS = {
        "number": 1.5,      # № п/п
        "start_time": 2.5,  # Тайм-код начала
        "end_time": 2.5,    # Тайм-код конца
        "shot_type": 2.0,   # Тип плана
        "description": 6.0, # Описание
        "dialogue": 4.0     # Текст/Диалоги
    }
    
    # Standard fonts for different elements
    FONTS = {
        "header": ("Times New Roman", 14, True),   # Font, size, bold
        "table_header": ("Times New Roman", 11, True),
        "table_content": ("Times New Roman", 10, False),
        "metadata": ("Times New Roman", 12, False)
    }
    
    def __init__(self):
        """Initialize DOCX template service."""
        self.template_path = None
        
    def create_document_template(self) -> Document:
        """
        Create a new document with Госфильмфонд template formatting.
        
        Returns:
            Document object with template formatting
        """
        doc = Document()
        
        # Set document margins (2.5cm on all sides)
        sections = doc.sections
        for section in sections:
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(2.5)
            section.right_margin = Cm(2.5)
        
        return doc
    
    def add_document_header(self, doc: Document, film_metadata: FilmMetadata) -> None:
        """
        Add document header with film information in GFF format.
        
        Args:
            doc: Document object
            film_metadata: Film metadata information
        """
        # Add empty line at the top
        doc.add_paragraph()
        
        # Add main title
        title_paragraph = doc.add_paragraph()
        title_run = title_paragraph.add_run("Форма монтажных листов фильма")
        font_name, font_size, is_bold = self.FONTS["header"]
        title_run.font.name = font_name
        title_run.font.size = Pt(font_size)
        title_run.bold = is_bold
        title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add empty lines
        for _ in range(11):
            doc.add_paragraph()
    
    def add_film_metadata_section(self, doc: Document, film_metadata: FilmMetadata) -> None:
        """
        Add film metadata section as GFF-style table.
        
        Args:
            doc: Document object
            film_metadata: Film metadata information
        """
        # Create metadata table (8 rows x 4 columns like in GFF format)
        metadata_table = doc.add_table(rows=8, cols=4)
        metadata_table.style = 'Table Grid'
        
        font_name, font_size, _ = self.FONTS["metadata"]
        
        # Row 0: Фирма-производитель
        row0 = metadata_table.rows[0]
        row0.cells[0].text = "Фирма-производитель"
        row0.cells[1].text = film_metadata.production_company
        
        # Row 1: Год выпуска / Страна производства
        row1 = metadata_table.rows[1]
        row1.cells[0].text = f"Год выпуска\nСтрана производства"
        row1.cells[1].text = f"{film_metadata.year}\n{film_metadata.country}"
        
        # Row 2: Автор(ы) сценария
        row2 = metadata_table.rows[2]
        row2.cells[0].text = "Автор (ы) сценария"
        row2.cells[1].text = ", ".join(film_metadata.screenwriters)
        
        # Row 3: Правообладатель(и)
        row3 = metadata_table.rows[3]
        row3.cells[0].text = "Правообладатель (и)"
        row3.cells[1].text = ", ".join(film_metadata.copyright_holders)
        
        # Row 4: Продолжительность / Количество серий
        row4 = metadata_table.rows[4]
        row4.cells[0].text = "Продолжительность фильма  (час:мин:сек) или (час:мин:сек:кадр)\nКоличество серий"
        row4.cells[1].text = f"{film_metadata.duration}\n{film_metadata.episodes_count}"
        # Merge cells 0 and 1 in row 4
        row4.cells[0].merge(row4.cells[1])
        
        # Row 5: Формат / Цвет / Носитель / Язык оригинала
        row5 = metadata_table.rows[5]
        row5.cells[0].text = f"Формат (кадра)\n{film_metadata.color_type.value}\nНоситель информации\nЯзык оригинала"
        row5.cells[1].text = f"{film_metadata.format}\n\n{film_metadata.media_carrier}\n{film_metadata.original_language}"
        
        # Row 6: Язык надписей
        row6 = metadata_table.rows[6]
        row6.cells[0].text = "Язык надписей"
        row6.cells[1].text = film_metadata.subtitle_language or ""
        
        # Row 7: Язык фонограммы
        row7 = metadata_table.rows[7]
        row7.cells[0].text = "Язык фонограммы"
        row7.cells[1].text = film_metadata.audio_language
        
        # Format all cells
        for row in metadata_table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.name = font_name
                        run.font.size = Pt(font_size)
        
        # Add empty lines after metadata table
        for _ in range(3):
            doc.add_paragraph()
    
    def add_montage_section_header(self, doc: Document, film_metadata: FilmMetadata) -> None:
        """
        Add montage section header in GFF format.
        
        Args:
            doc: Document object
            film_metadata: Film metadata information
        """
        # Add "МОНТАЖНЫЕ ЛИСТЫ" title
        title_paragraph = doc.add_paragraph()
        title_run = title_paragraph.add_run("МОНТАЖНЫЕ ЛИСТЫ")
        font_name, font_size, is_bold = self.FONTS["header"]
        title_run.font.name = font_name
        title_run.font.size = Pt(font_size)
        title_run.bold = is_bold
        title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add empty line
        doc.add_paragraph()
        
        # Add film title in quotes
        film_title_paragraph = doc.add_paragraph()
        film_title_run = film_title_paragraph.add_run(f'«{film_metadata.title}»')
        film_title_run.font.name = font_name
        film_title_run.font.size = Pt(font_size - 1)
        film_title_run.bold = is_bold
        film_title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add subtitle with original language title
        subtitle_paragraph = doc.add_paragraph()
        subtitle_text = f"(название фильма на языке оригинала)"
        subtitle_run = subtitle_paragraph.add_run(subtitle_text)
        subtitle_run.font.name = font_name
        subtitle_run.font.size = Pt(font_size - 4)
        subtitle_run.italic = True
        subtitle_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add empty lines
        for _ in range(15):
            doc.add_paragraph()

    def create_montage_table(self, doc: Document, montage_rows: List[MontageRow]) -> None:
        """
        Create montage table in GFF format.
        
        Args:
            doc: Document object
            montage_rows: List of montage rows to include in table
        """
        if not montage_rows:
            logger.warning("No montage rows provided for table creation")
            return
        
        # Create table with header row (6 columns like in GFF format)
        table = doc.add_table(rows=1, cols=6)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Set table style
        table.style = 'Table Grid'
        
        # Configure header row with GFF format headers
        header_cells = table.rows[0].cells
        headers = [
            "№\nплана",
            "Начальный тайм-код плана\n(часы: мин.: сек.: кадры)",
            "Конечный тайм-код плана\n(часы: мин.: сек.: кадры)", 
            "Вид плана",
            "Содержание (описание) плана, титры",
            "Монологи, разговоры, песни, субтитры\n  Музыка."
        ]
        
        font_name, font_size, is_bold = self.FONTS["table_header"]
        
        for i, header_text in enumerate(headers):
            cell = header_cells[i]
            cell.text = header_text
            
            # Format header cell
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            run = paragraph.runs[0]
            run.font.name = font_name
            run.font.size = Pt(font_size)
            run.bold = is_bold
            
            # Set cell vertical alignment
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        
        # Set column widths for GFF format
        gff_column_widths = [1.5, 3.0, 3.0, 2.0, 6.0, 4.0]  # Adjusted for GFF format
        for i, width_cm in enumerate(gff_column_widths):
            for row in table.rows:
                row.cells[i].width = Cm(width_cm)
        
        # Add data rows
        content_font_name, content_font_size, content_is_bold = self.FONTS["table_content"]
        
        for montage_row in montage_rows:
            row_cells = table.add_row().cells
            
            # Prepare row data
            row_data = [
                str(montage_row.number),
                montage_row.start_timecode,
                montage_row.end_timecode,
                self._format_shot_type(montage_row),
                self._format_description(montage_row),
                self._format_dialogue(montage_row)
            ]
            
            # Fill cells
            for i, cell_text in enumerate(row_data):
                cell = row_cells[i]
                cell.text = cell_text
                
                # Format cell content
                paragraph = cell.paragraphs[0]
                
                # Set alignment based on column
                if i in [0, 1, 2, 3]:  # Number, timecodes, shot type - center aligned
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                else:  # Description, dialogue - left aligned
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                
                # Format font
                for run in paragraph.runs:
                    run.font.name = content_font_name
                    run.font.size = Pt(content_font_size)
                    run.bold = content_is_bold
                
                # Set cell vertical alignment
                cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    
    def _format_shot_type(self, montage_row: MontageRow) -> str:
        """
        Format shot type for display in table.
        
        Args:
            montage_row: Montage row data
            
        Returns:
            Formatted shot type string
        """
        # Convert shot type to abbreviated form
        shot_type_abbrev = {
            "Дальний": "Дальн.",
            "Общий": "Общ.",
            "Средний": "Ср.",
            "Крупный": "Крупн.",
            "Деталь": "Дет."
        }
        
        shot_type_str = montage_row.shot_type.value
        return shot_type_abbrev.get(shot_type_str, shot_type_str)
    
    def _format_description(self, montage_row: MontageRow) -> str:
        """
        Format description with special tags.
        
        Args:
            montage_row: Montage row data
            
        Returns:
            Formatted description string
        """
        description = montage_row.description
        
        # Add special tags if present
        if montage_row.special_tags:
            tags_str = ", ".join(montage_row.special_tags)
            description = f"{description} ({tags_str})"
        
        return description
    
    def _format_dialogue(self, montage_row: MontageRow) -> str:
        """
        Format dialogue with speaker information.
        
        Args:
            montage_row: Montage row data
            
        Returns:
            Formatted dialogue string
        """
        if not montage_row.dialogue.strip():
            return ""
        
        dialogue = montage_row.dialogue
        
        # Add speaker if specified
        if montage_row.speaker:
            dialogue = f"{montage_row.speaker}: {dialogue}"
        
        return dialogue
    
    def add_document_header_footer(
        self, 
        doc: Document, 
        film_metadata: FilmMetadata,
        project_settings: Optional[ProjectSettings] = None
    ) -> None:
        """
        Add document header and footer with film metadata.
        
        Args:
            doc: Document object
            film_metadata: Film metadata information
            project_settings: Optional project settings
        """
        # Get the first section
        section = doc.sections[0]
        
        # Add header
        header = section.header
        header_paragraph = header.paragraphs[0]
        
        # Header content with film metadata
        header_text = f"{film_metadata.title} | {film_metadata.production_company} | {film_metadata.year}"
        header_run = header_paragraph.add_run(header_text)
        
        font_name, font_size, _ = self.FONTS["metadata"]
        header_run.font.name = font_name
        header_run.font.size = Pt(font_size - 2)
        header_run.italic = True
        
        header_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add footer
        footer = section.footer
        footer_paragraph = footer.paragraphs[0]
        
        # Footer content with generation info and technical details
        generation_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        footer_text = f"Монтажный лист создан автоматически {generation_time}"
        
        if project_settings:
            footer_text += f" | {project_settings.standard.value} | {project_settings.fps} fps"
        
        footer_text += f" | Формат: {film_metadata.format} | {film_metadata.color_type.value}"
        
        footer_run = footer_paragraph.add_run(footer_text)
        footer_run.font.name = font_name
        footer_run.font.size = Pt(font_size - 3)
        footer_run.italic = True
        
        footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    def add_document_footer(self, doc: Document, project_settings: Optional[ProjectSettings] = None) -> None:
        """
        Add document footer with generation information (legacy method).
        
        Args:
            doc: Document object
            project_settings: Optional project settings
        """
        # Add empty line
        doc.add_paragraph()
        
        # Add generation info
        footer_paragraph = doc.add_paragraph()
        
        generation_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        footer_text = f"Документ создан автоматически {generation_time}"
        
        if project_settings:
            footer_text += f" | Стандарт: {project_settings.standard.value}"
            footer_text += f" | Частота кадров: {project_settings.fps} fps"
        
        footer_run = footer_paragraph.add_run(footer_text)
        font_name, font_size, _ = self.FONTS["table_content"]
        footer_run.font.name = font_name
        footer_run.font.size = Pt(font_size - 1)
        footer_run.italic = True
        
        footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    def add_gff_document_footer(self, doc: Document) -> None:
        """
        Add GFF-style document footer with signature and stamp.
        
        Args:
            doc: Document object
        """
        # Add empty lines
        for _ in range(3):
            doc.add_paragraph()
        
        # Add compliance statement
        compliance_paragraph = doc.add_paragraph()
        compliance_text = "Монтажные листы соответствуют копии  фильма, принятого к выпуску на    экран."
        compliance_run = compliance_paragraph.add_run(compliance_text)
        font_name, font_size, _ = self.FONTS["metadata"]
        compliance_run.font.name = font_name
        compliance_run.font.size = Pt(font_size)
        
        # Add empty lines
        for _ in range(2):
            doc.add_paragraph()
        
        # Add signature line
        signature_paragraph = doc.add_paragraph()
        signature_text = "Руководитель организации  ____________   _________________       ____________"
        signature_run = signature_paragraph.add_run(signature_text)
        signature_run.font.name = font_name
        signature_run.font.size = Pt(font_size)
        
        # Add signature description
        signature_desc_paragraph = doc.add_paragraph()
        signature_desc_text = "                                                                        подпись        расшифровка подписи                     дата"
        signature_desc_run = signature_desc_paragraph.add_run(signature_desc_text)
        signature_desc_run.font.name = font_name
        signature_desc_run.font.size = Pt(font_size - 2)
        
        # Add stamp placeholder
        stamp_paragraph = doc.add_paragraph()
        stamp_text = "М.П."
        stamp_run = stamp_paragraph.add_run(stamp_text)
        stamp_run.font.name = font_name
        stamp_run.font.size = Pt(font_size)
    
    def add_production_information_section(self, doc: Document, film_metadata: FilmMetadata) -> None:
        """
        Add detailed production information section.
        
        Args:
            doc: Document object
            film_metadata: Film metadata information
        """
        # Add section title
        section_title = doc.add_paragraph()
        title_run = section_title.add_run("ПРОИЗВОДСТВЕННАЯ ИНФОРМАЦИЯ")
        font_name, font_size, is_bold = self.FONTS["table_header"]
        title_run.font.name = font_name
        title_run.font.size = Pt(font_size)
        title_run.bold = is_bold
        section_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add empty line
        doc.add_paragraph()
        
        # Create production info table
        prod_table = doc.add_table(rows=0, cols=2)
        prod_table.style = 'Table Grid'
        
        # Production information items
        production_items = [
            ("Правообладатели:", ", ".join(film_metadata.copyright_holders)),
            ("Авторы сценария:", ", ".join(film_metadata.screenwriters)),
            ("Количество серий:", str(film_metadata.episodes_count)),
            ("Носитель:", film_metadata.media_carrier),
            ("Язык оригинала:", film_metadata.original_language),
            ("Язык звука:", film_metadata.audio_language)
        ]
        
        # Add subtitle language if specified
        if film_metadata.subtitle_language:
            production_items.append(("Язык субтитров:", film_metadata.subtitle_language))
        
        font_name, font_size, _ = self.FONTS["metadata"]
        
        for label, value in production_items:
            row_cells = prod_table.add_row().cells
            
            # Label cell
            label_cell = row_cells[0]
            label_cell.text = label
            label_paragraph = label_cell.paragraphs[0]
            label_run = label_paragraph.runs[0]
            label_run.font.name = font_name
            label_run.font.size = Pt(font_size)
            label_run.bold = True
            
            # Value cell
            value_cell = row_cells[1]
            value_cell.text = value
            value_paragraph = value_cell.paragraphs[0]
            value_run = value_paragraph.runs[0]
            value_run.font.name = font_name
            value_run.font.size = Pt(font_size)
            value_run.bold = False
        
        # Set column widths
        for row in prod_table.rows:
            row.cells[0].width = Cm(4.0)  # Label column
            row.cells[1].width = Cm(8.0)  # Value column
        
        # Add empty line after table
        doc.add_paragraph()
    
    def add_compliance_information(self, doc: Document, film_metadata: FilmMetadata) -> None:
        """
        Add compliance information section for Госфильмфонд requirements.
        
        Args:
            doc: Document object
            film_metadata: Film metadata information
        """
        # Add compliance section
        compliance_paragraph = doc.add_paragraph()
        
        compliance_text = (
            f"Настоящий монтажный лист составлен в соответствии с требованиями "
            f"Госфильмфонда Российской Федерации для фильма \"{film_metadata.title}\" "
            f"производства {film_metadata.production_company} ({film_metadata.year} г., {film_metadata.country}). "
            f"Продолжительность: {film_metadata.duration}, формат: {film_metadata.format}, "
            f"{film_metadata.color_type.value.lower()}."
        )
        
        compliance_run = compliance_paragraph.add_run(compliance_text)
        font_name, font_size, _ = self.FONTS["metadata"]
        compliance_run.font.name = font_name
        compliance_run.font.size = Pt(font_size - 1)
        compliance_run.italic = True
        
        compliance_paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        
        # Add empty line
        doc.add_paragraph()


class DOCXGeneratorService:
    """Main service for generating DOCX documents."""
    
    def __init__(self):
        """Initialize DOCX generator service."""
        self.template_service = DOCXTemplateService()
    
    async def generate_montage_docx(
        self,
        montage_rows: List[MontageRow],
        film_metadata: FilmMetadata,
        project_settings: Optional[ProjectSettings] = None,
        use_gff_format: bool = True,
        include_production_info: bool = False,
        include_compliance_info: bool = False
    ) -> bytes:
        """
        Generate complete montage DOCX document.
        
        Args:
            montage_rows: List of montage rows
            film_metadata: Film metadata information
            project_settings: Optional project settings
            use_gff_format: Whether to use GFF (Госфильмфонд) format
            include_production_info: Whether to include detailed production information (legacy)
            include_compliance_info: Whether to include compliance information (legacy)
            
        Returns:
            DOCX document as bytes
        """
        try:
            logger.info(f"Generating DOCX document for {len(montage_rows)} montage rows")
            
            # Create document
            doc = self.template_service.create_document_template()
            
            if use_gff_format:
                # GFF Format
                # 1. Document header
                self.template_service.add_document_header(doc, film_metadata)
                
                # 2. Film metadata table
                self.template_service.add_film_metadata_section(doc, film_metadata)
                
                # 3. Montage section header
                self.template_service.add_montage_section_header(doc, film_metadata)
                
                # 4. Montage table
                self.template_service.create_montage_table(doc, montage_rows)
                
                # 5. GFF footer with signature
                self.template_service.add_gff_document_footer(doc)
                
            else:
                # Legacy format
                # Add document header and footer with metadata
                self.template_service.add_document_header_footer(doc, film_metadata, project_settings)
                
                # Add document sections
                self.template_service.add_document_header(doc, film_metadata)
                self.template_service.add_film_metadata_section(doc, film_metadata)
                
                # Add production information if requested
                if include_production_info:
                    self.template_service.add_production_information_section(doc, film_metadata)
                
                # Add compliance information if requested
                if include_compliance_info:
                    self.template_service.add_compliance_information(doc, film_metadata)
                
                # Add montage table
                self.template_service.create_montage_table(doc, montage_rows)
                
                # Add document footer (in body)
                self.template_service.add_document_footer(doc, project_settings)
            
            # Convert to bytes
            doc_bytes = await self._document_to_bytes(doc)
            
            logger.info("DOCX document generation completed successfully")
            return doc_bytes
            
        except Exception as e:
            logger.error(f"DOCX generation failed: {e}")
            raise DOCXGenerationError(f"Failed to generate DOCX document: {e}")
    
    async def _document_to_bytes(self, doc: Document) -> bytes:
        """
        Convert Document object to bytes.
        
        Args:
            doc: Document object
            
        Returns:
            Document as bytes
        """
        # Use BytesIO to save document to memory
        doc_buffer = BytesIO()
        doc.save(doc_buffer)
        doc_buffer.seek(0)
        
        return doc_buffer.getvalue()
    
    async def save_document_to_file(
        self,
        montage_rows: List[MontageRow],
        film_metadata: FilmMetadata,
        output_path: str,
        project_settings: Optional[ProjectSettings] = None,
        use_gff_format: bool = True,
        include_production_info: bool = False,
        include_compliance_info: bool = False
    ) -> str:
        """
        Generate and save DOCX document to file.
        
        Args:
            montage_rows: List of montage rows
            film_metadata: Film metadata information
            output_path: Path where to save the document
            project_settings: Optional project settings
            
        Returns:
            Path to saved document
        """
        try:
            # Generate document bytes
            doc_bytes = await self.generate_montage_docx(
                montage_rows, film_metadata, project_settings,
                use_gff_format, include_production_info, include_compliance_info
            )
            
            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(doc_bytes)
            
            logger.info(f"DOCX document saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to save DOCX document: {e}")
            raise DOCXGenerationError(f"Failed to save DOCX document: {e}")
    
    async def validate_document_compliance(
        self,
        montage_rows: List[MontageRow],
        film_metadata: FilmMetadata,
        project_settings: Optional[ProjectSettings] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate document compliance with Госфильмфонд requirements.
        
        Args:
            montage_rows: List of montage rows to validate
            film_metadata: Film metadata to validate
            project_settings: Optional project settings to validate
            
        Returns:
            Tuple of (is_compliant, list_of_issues)
        """
        issues = []
        
        # Validate film metadata completeness
        metadata_issues = await self._validate_film_metadata(film_metadata)
        issues.extend(metadata_issues)
        
        # Validate montage rows
        montage_issues = await self._validate_montage_rows(montage_rows)
        issues.extend(montage_issues)
        
        # Validate project settings if provided
        if project_settings:
            settings_issues = await self._validate_project_settings(project_settings)
            issues.extend(settings_issues)
        
        # Validate document structure compliance
        structure_issues = await self._validate_document_structure(montage_rows, film_metadata)
        issues.extend(structure_issues)
        
        is_compliant = len(issues) == 0
        
        if is_compliant:
            logger.info("Document validation passed - compliant with requirements")
        else:
            logger.warning(f"Document validation found {len(issues)} issues")
        
        return is_compliant, issues
    
    async def validate_goskino_compliance(
        self,
        montage_rows: List[MontageRow],
        film_metadata: FilmMetadata,
        project_settings: Optional[ProjectSettings] = None
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate compliance specifically with Госфильмфонд requirements.
        
        Args:
            montage_rows: List of montage rows to validate
            film_metadata: Film metadata to validate
            project_settings: Optional project settings to validate
            
        Returns:
            Tuple of (is_compliant, list_of_issues, compliance_report)
        """
        issues = []
        compliance_report = {
            "validation_date": datetime.now().isoformat(),
            "film_title": film_metadata.title,
            "total_rows": len(montage_rows),
            "compliance_checks": {}
        }
        
        # Check required metadata fields for Госфильмфонд
        goskino_metadata_issues = await self._validate_goskino_metadata(film_metadata)
        issues.extend(goskino_metadata_issues)
        compliance_report["compliance_checks"]["metadata"] = len(goskino_metadata_issues) == 0
        
        # Check timecode format compliance
        timecode_issues = await self._validate_goskino_timecodes(montage_rows, project_settings)
        issues.extend(timecode_issues)
        compliance_report["compliance_checks"]["timecodes"] = len(timecode_issues) == 0
        
        # Check table structure compliance
        structure_issues = await self._validate_goskino_table_structure(montage_rows)
        issues.extend(structure_issues)
        compliance_report["compliance_checks"]["table_structure"] = len(structure_issues) == 0
        
        # Check content completeness
        content_issues = await self._validate_goskino_content(montage_rows, film_metadata)
        issues.extend(content_issues)
        compliance_report["compliance_checks"]["content"] = len(content_issues) == 0
        
        is_compliant = len(issues) == 0
        compliance_report["is_compliant"] = is_compliant
        compliance_report["total_issues"] = len(issues)
        
        return is_compliant, issues, compliance_report
    
    async def _validate_film_metadata(self, film_metadata: FilmMetadata) -> List[str]:
        """
        Validate film metadata for completeness.
        
        Args:
            film_metadata: Film metadata to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        
        # Required fields
        required_fields = [
            ("title", "Название фильма"),
            ("production_company", "Производитель"),
            ("country", "Страна"),
            ("duration", "Продолжительность"),
            ("format", "Формат"),
            ("media_carrier", "Носитель")
        ]
        
        for field_name, field_label in required_fields:
            value = getattr(film_metadata, field_name, None)
            if not value or (isinstance(value, str) and not value.strip()):
                issues.append(f"Отсутствует обязательное поле: {field_label}")
        
        # Validate year range
        if film_metadata.year < 1900 or film_metadata.year > 2100:
            issues.append(f"Некорректный год производства: {film_metadata.year}")
        
        # Validate screenwriters and copyright holders
        if not film_metadata.screenwriters:
            issues.append("Не указаны авторы сценария")
        
        if not film_metadata.copyright_holders:
            issues.append("Не указаны правообладатели")
        
        # Validate duration format (should be HH:MM:SS)
        duration_pattern = r'^\d{1,2}:\d{2}:\d{2}$'
        import re
        if not re.match(duration_pattern, film_metadata.duration):
            issues.append(f"Некорректный формат продолжительности: {film_metadata.duration} (ожидается ЧЧ:ММ:СС)")
        
        return issues
    
    async def _validate_montage_rows(self, montage_rows: List[MontageRow]) -> List[str]:
        """
        Validate montage rows for completeness and consistency.
        
        Args:
            montage_rows: List of montage rows to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        
        if not montage_rows:
            issues.append("Отсутствуют строки монтажного листа")
            return issues
        
        # Validate row numbering
        for i, row in enumerate(montage_rows):
            expected_number = i + 1
            if row.number != expected_number:
                issues.append(f"Некорректная нумерация строки {i + 1}: {row.number}")
        
        # Validate timecode format
        timecode_pattern = r'^\d{2}:\d{2}:\d{2}:\d{2}$'
        import re
        
        for i, row in enumerate(montage_rows):
            if not re.match(timecode_pattern, row.start_timecode):
                issues.append(f"Строка {i + 1}: Некорректный формат начального таймкода: {row.start_timecode}")
            
            if not re.match(timecode_pattern, row.end_timecode):
                issues.append(f"Строка {i + 1}: Некорректный формат конечного таймкода: {row.end_timecode}")
            
            # Validate required fields
            if not row.description.strip():
                issues.append(f"Строка {i + 1}: Отсутствует описание")
        
        return issues
    
    async def get_document_statistics(
        self,
        montage_rows: List[MontageRow]
    ) -> Dict[str, Any]:
        """
        Generate statistics about the document content.
        
        Args:
            montage_rows: List of montage rows
            
        Returns:
            Dictionary with document statistics
        """
        if not montage_rows:
            return {"total_rows": 0}
        
        # Count shot types
        shot_type_counts = {}
        for row in montage_rows:
            shot_type = row.shot_type.value
            shot_type_counts[shot_type] = shot_type_counts.get(shot_type, 0) + 1
        
        # Count rows with dialogue
        rows_with_dialogue = sum(1 for row in montage_rows if row.dialogue.strip())
        
        # Count rows with music
        rows_with_music = sum(1 for row in montage_rows if row.has_music)
        
        # Count special tags
        special_tag_counts = {}
        for row in montage_rows:
            for tag in row.special_tags:
                special_tag_counts[tag] = special_tag_counts.get(tag, 0) + 1
        
        # Count unique speakers
        unique_speakers = set()
        for row in montage_rows:
            if row.speaker:
                unique_speakers.add(row.speaker)
        
        return {
            "total_rows": len(montage_rows),
            "shot_type_distribution": shot_type_counts,
            "rows_with_dialogue": rows_with_dialogue,
            "dialogue_coverage_percent": (rows_with_dialogue / len(montage_rows)) * 100,
            "rows_with_music": rows_with_music,
            "music_coverage_percent": (rows_with_music / len(montage_rows)) * 100,
            "special_tag_distribution": special_tag_counts,
            "unique_speakers": len(unique_speakers),
            "speaker_list": sorted(list(unique_speakers))
        } 
   
    async def _validate_project_settings(self, project_settings: ProjectSettings) -> List[str]:
        """
        Validate project settings for compliance.
        
        Args:
            project_settings: Project settings to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        
        # Validate timecode start format
        timecode_pattern = r'^\d{2}:\d{2}:\d{2}:\d{2}$'
        import re
        if not re.match(timecode_pattern, project_settings.timecode_start):
            issues.append(f"Некорректный формат стартового таймкода: {project_settings.timecode_start}")
        
        # Validate FPS
        valid_fps_values = [23.976, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0]
        if project_settings.fps not in valid_fps_values:
            issues.append(f"Неподдерживаемая частота кадров: {project_settings.fps}")
        
        # Validate standard
        valid_standards = ["ГФФ", "Красногорский"]
        standard_value = project_settings.standard.value if hasattr(project_settings.standard, 'value') else project_settings.standard
        if standard_value not in valid_standards:
            issues.append(f"Неподдерживаемый стандарт: {standard_value}")
        
        return issues
    
    async def _validate_document_structure(
        self, 
        montage_rows: List[MontageRow], 
        film_metadata: FilmMetadata
    ) -> List[str]:
        """
        Validate document structure for compliance.
        
        Args:
            montage_rows: List of montage rows
            film_metadata: Film metadata
            
        Returns:
            List of validation issues
        """
        issues = []
        
        # Check minimum number of rows
        if len(montage_rows) < 1:
            issues.append("Документ должен содержать минимум одну строку монтажного листа")
        
        # Check maximum reasonable number of rows
        if len(montage_rows) > 10000:
            issues.append(f"Слишком много строк в монтажном листе: {len(montage_rows)} (максимум 10000)")
        
        # Check for duplicate row numbers
        row_numbers = [row.number for row in montage_rows]
        if len(set(row_numbers)) != len(row_numbers):
            issues.append("Обнаружены дублирующиеся номера строк")
        
        # Check timecode continuity
        for i in range(1, len(montage_rows)):
            prev_row = montage_rows[i - 1]
            current_row = montage_rows[i]
            
            # Simple check that current start is after or equal to previous end
            if current_row.start_timecode < prev_row.end_timecode:
                issues.append(f"Строка {current_row.number}: Нарушена последовательность таймкодов")
        
        return issues
    
    async def _validate_goskino_metadata(self, film_metadata: FilmMetadata) -> List[str]:
        """
        Validate metadata specifically for Госфильмфонд requirements.
        
        Args:
            film_metadata: Film metadata to validate
            
        Returns:
            List of validation issues
        """
        issues = []
        
        # Госфильмфонд specific requirements
        goskino_required_fields = [
            ("title", "Название фильма"),
            ("production_company", "Производитель"),
            ("country", "Страна производства"),
            ("duration", "Продолжительность"),
            ("format", "Формат"),
            ("media_carrier", "Носитель"),
            ("original_language", "Язык оригинала"),
            ("audio_language", "Язык звука")
        ]
        
        for field_name, field_label in goskino_required_fields:
            value = getattr(film_metadata, field_name, None)
            if not value or (isinstance(value, str) and not value.strip()):
                issues.append(f"Госфильмфонд: Отсутствует обязательное поле '{field_label}'")
        
        # Check that screenwriters and copyright holders are not empty
        if not film_metadata.screenwriters or len(film_metadata.screenwriters) == 0:
            issues.append("Госфильмфонд: Должен быть указан минимум один автор сценария")
        
        if not film_metadata.copyright_holders or len(film_metadata.copyright_holders) == 0:
            issues.append("Госфильмфонд: Должен быть указан минимум один правообладатель")
        
        # Validate Russian content requirements
        if film_metadata.country == "Россия":
            if film_metadata.original_language != "Русский":
                issues.append("Госфильмфонд: Для российских фильмов язык оригинала должен быть 'Русский'")
        
        return issues
    
    async def _validate_goskino_timecodes(
        self, 
        montage_rows: List[MontageRow],
        project_settings: Optional[ProjectSettings]
    ) -> List[str]:
        """
        Validate timecodes for Госфильмфонд compliance.
        
        Args:
            montage_rows: List of montage rows
            project_settings: Optional project settings
            
        Returns:
            List of validation issues
        """
        issues = []
        
        if not montage_rows:
            return issues
        
        # Check timecode format compliance
        timecode_pattern = r'^\d{2}:\d{2}:\d{2}:\d{2}$'
        import re
        
        for i, row in enumerate(montage_rows):
            if not re.match(timecode_pattern, row.start_timecode):
                issues.append(f"Госфильмфонд: Строка {i + 1} - некорректный формат начального таймкода")
            
            if not re.match(timecode_pattern, row.end_timecode):
                issues.append(f"Госфильмфонд: Строка {i + 1} - некорректный формат конечного таймкода")
        
        # Check that first timecode starts appropriately
        if project_settings and montage_rows:
            first_row = montage_rows[0]
            expected_start = project_settings.timecode_start
            
            # Allow some flexibility in start time
            if not first_row.start_timecode.startswith(expected_start[:8]):  # Check HH:MM:SS part
                issues.append(f"Госфильмфонд: Первый таймкод должен начинаться близко к {expected_start}")
        
        return issues
    
    async def _validate_goskino_table_structure(self, montage_rows: List[MontageRow]) -> List[str]:
        """
        Validate table structure for Госфильмфонд compliance.
        
        Args:
            montage_rows: List of montage rows
            
        Returns:
            List of validation issues
        """
        issues = []
        
        if not montage_rows:
            return issues
        
        # Check required columns have content
        for i, row in enumerate(montage_rows):
            # Row number must be sequential
            expected_number = i + 1
            if row.number != expected_number:
                issues.append(f"Госфильмфонд: Строка {i + 1} - некорректная нумерация ({row.number})")
            
            # Description is required
            if not row.description or not row.description.strip():
                issues.append(f"Госфильмфонд: Строка {i + 1} - отсутствует описание")
            
            # Shot type must be valid
            valid_shot_types = ["Дальний", "Общий", "Средний", "Крупный", "Деталь"]
            shot_type_value = row.shot_type.value if hasattr(row.shot_type, 'value') else str(row.shot_type)
            if shot_type_value not in valid_shot_types:
                issues.append(f"Госфильмфонд: Строка {i + 1} - некорректный тип плана ({shot_type_value})")
        
        return issues
    
    async def _validate_goskino_content(
        self, 
        montage_rows: List[MontageRow], 
        film_metadata: FilmMetadata
    ) -> List[str]:
        """
        Validate content completeness for Госфильмфонд compliance.
        
        Args:
            montage_rows: List of montage rows
            film_metadata: Film metadata
            
        Returns:
            List of validation issues
        """
        issues = []
        
        if not montage_rows:
            return issues
        
        # Check content coverage
        rows_with_description = sum(1 for row in montage_rows if row.description.strip())
        description_coverage = rows_with_description / len(montage_rows)
        
        if description_coverage < 0.95:  # 95% of rows should have descriptions
            issues.append(f"Госфильмфонд: Недостаточное покрытие описаниями ({description_coverage:.1%})")
        
        # Check for reasonable distribution of shot types
        shot_type_counts = {}
        for row in montage_rows:
            shot_type = row.shot_type.value if hasattr(row.shot_type, 'value') else str(row.shot_type)
            shot_type_counts[shot_type] = shot_type_counts.get(shot_type, 0) + 1
        
        # Warn if only one shot type is used (might indicate processing error)
        if len(shot_type_counts) == 1 and len(montage_rows) > 10:
            issues.append("Госфильмфонд: Подозрительно однообразные типы планов")
        
        # Check for excessively long scenes (might indicate detection errors)
        long_scenes = 0
        for row in montage_rows:
            # Rough duration check based on timecode difference
            start_parts = row.start_timecode.split(':')
            end_parts = row.end_timecode.split(':')
            
            try:
                start_seconds = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60 + int(start_parts[2])
                end_seconds = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60 + int(end_parts[2])
                duration = end_seconds - start_seconds
                
                if duration > 300:  # More than 5 minutes
                    long_scenes += 1
            except (ValueError, IndexError):
                pass  # Skip if timecode parsing fails
        
        if long_scenes > len(montage_rows) * 0.1:  # More than 10% of scenes are very long
            issues.append("Госфильмфонд: Обнаружены подозрительно длинные сцены")
        
        return issues
    
    async def generate_docx_for_task(
        self,
        task_id: str,
        montage_rows: List[Dict[str, Any]],
        film_metadata: Dict[str, Any],
        project_settings: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate DOCX file for a specific task and save it to the output directory.
        
        Args:
            task_id: ID of the processing task
            montage_rows: List of montage rows as dictionaries
            film_metadata: Film metadata as dictionary
            project_settings: Optional project settings as dictionary
            
        Returns:
            Path to the generated DOCX file
        """
        try:
            # Convert dictionaries to Pydantic models
            from app.schemas.film_project import MontageRow, FilmMetadata, ProjectSettings
            
            # Convert montage rows
            montage_row_objects = []
            for row_data in montage_rows:
                montage_row_objects.append(MontageRow(**row_data))
            
            # Convert film metadata
            film_metadata_obj = FilmMetadata(**film_metadata)
            
            # Convert project settings if provided
            project_settings_obj = None
            if project_settings:
                project_settings_obj = ProjectSettings(**project_settings)
            
            # Determine output path
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            output_filename = f"montage_list_{task_id}.docx"
            output_path = output_dir / output_filename
            
            # Generate and save document
            await self.save_document_to_file(
                montage_rows=montage_row_objects,
                film_metadata=film_metadata_obj,
                output_path=str(output_path),
                project_settings=project_settings_obj,
                use_gff_format=True
            )
            
            logger.info(f"Generated DOCX for task {task_id}: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to generate DOCX for task {task_id}: {e}")
            raise DOCXGenerationError(f"Failed to generate DOCX for task {task_id}: {e}")


# Create global instance
docx_generator = DOCXGeneratorService()