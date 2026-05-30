"""Template Skill — learn and evolve a template library from completed game projects.

Pipeline: Collect → Classify → Extract → Abstract → Merge → Save.
"""

from pathlib import Path

from opengame.core.llm_client import BaseLlmClient
from opengame.skills.template_skill.abstractor import Abstractor
from opengame.skills.template_skill.classifier import Classifier
from opengame.skills.template_skill.collector import ProjectCollector
from opengame.skills.template_skill.extractor import PatternExtractor
from opengame.skills.template_skill.library_manager import LibraryManager
from opengame.skills.template_skill.merger import FamilyMerger
from opengame.skills.template_skill.types import TemplateLibrary


class TemplateSkill:
    """Orchestrator for the complete template evolution pipeline.

    Usage:
        skill = TemplateSkill(llm_client, library_manager)
        library = await skill.evolve(Path("./my-game"), task_id="task-001")
    """

    def __init__(
        self,
        llm_client: BaseLlmClient,
        library_manager: LibraryManager,
    ) -> None:
        self.llm_client = llm_client
        self.library_manager = library_manager

        # Initialize sub-components
        self.collector = ProjectCollector()
        self.classifier = Classifier(llm_client)
        self.extractor = PatternExtractor()
        self.abstractor = Abstractor(llm_client)
        self.merger = FamilyMerger()

    async def evolve(self, project_dir: Path, task_id: str) -> TemplateLibrary:
        """Run the full template evolution pipeline.

        Pipeline steps:
        1. Collect — snapshot the project
        2. Classify — determine archetype
        3. Extract — identify patterns
        4. Abstract — generalize code
        5. Merge — integrate into library
        6. Save — persist updated library

        Args:
            project_dir: Path to the completed game project.
            task_id: Unique task identifier for the evolution log.

        Returns:
            The updated TemplateLibrary.
        """
        # Load current library
        library = await self.library_manager.load_or_init()

        # Step 1: Collect
        snapshot = await self.collector.collect(project_dir)

        # Step 2: Classify
        classification = await self.classifier.classify(snapshot, library)

        # Step 3: Extract patterns
        patterns = self.extractor.extract(snapshot, classification)

        # Step 4: Abstract templates
        abstracted = await self.abstractor.abstract(patterns)

        # Step 5: Merge into library
        library, family_id = self.merger.merge(
            abstracted, library, str(project_dir), task_id,
        )

        # Step 6: Save
        await self.library_manager.save(library)

        return library

    async def get_library_summary(self) -> str:
        """Get a human-readable summary of the template library.

        Returns:
            Summary string.
        """
        library = await self.library_manager.load_or_init()
        return self.library_manager.get_summary(library)
