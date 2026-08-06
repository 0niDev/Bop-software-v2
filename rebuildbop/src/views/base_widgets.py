"""Common base widgets for the ERP application."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QGridLayout,
)
from PySide6.QtCore import Qt


class KPICard(QFrame):
    """Key Performance Indicator card widget."""
    
    def __init__(self, title: str = "", value: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("kpi_card")
        self.setFixedHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.title_label = QLabel(title)
        self.title_label.setObjectName("kpi_title")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        
        self.value_label = QLabel(value)
        self.value_label.setObjectName("kpi_value")
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)
        
        layout.addStretch()


class SectionFrame(QFrame):
    """Section container with title."""
    
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("section_frame")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("section_title")
            title_label.setWordWrap(True)
            layout.addWidget(title_label)


class LoadingWidget(QWidget):
    """Placeholder loading indicator widget."""
    
    def __init__(self, message: str = "Loading...", parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(label)


class EmptyStateWidget(QWidget):
    """Empty state placeholder when no data exists."""
    
    def __init__(self, message: str = "No data available", parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #aaa; font-size: 13px;")
        layout.addWidget(label)


class PlaceholderView(QWidget):
    """Generic placeholder view for modules under development."""
    
    def __init__(self, module_name: str = "Module", parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel(module_name)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1a1a2e;")
        layout.addWidget(title)
        
        subtitle = QLabel("This module is under development")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #888; font-size: 14px; margin-top: 8px;")
        layout.addWidget(subtitle)
