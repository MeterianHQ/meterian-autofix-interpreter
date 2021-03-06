import os
import logging
from .PullRequestInterface import PullRequestInterface
from .RepositoryInterface import RepositoryInterface
from .BranchHelper import BranchHelper

class PrOrchestrator:

    SUPPORTED_MANIFESTFILES = [ "pom.xml", "composer.json", "Gemfile", "Gemfile.lock", "Pipfile", "Pipfile.lock", "package.json", "package-lock.json" ]

    PR_CONTENT_TITLE_KEY = "title"
    PR_CONTENT_BODY_KEY = "message"

    __log = logging.getLogger("PrOrchestrator")

    def __init__(self, repository: RepositoryInterface, author: dict):
        self.repo = repository
        self.branch_helper = BranchHelper()
        self.author = author

    def orchestarte(self, pr_text_content: dict, local_changes_relative_paths: list, base_branch: str, pdf_report_path: str = None):
        self.__log.debug("Changes detected were %s", str(local_changes_relative_paths))
        self.__log.debug("Will create branches and commit to these as appropriate...")

        for local_change_relative_path in local_changes_relative_paths:

            manifest_file_name = os.path.basename(local_change_relative_path)
            if not manifest_file_name in self.SUPPORTED_MANIFESTFILES:
                self.__log.debug("Ignoring changes on %s as the file is not a suppoerted manifest file", local_change_relative_path)
                continue

            pr_branch_ref = self.__create_pr_branch_ref(local_change_relative_path, base_branch)
            if pr_branch_ref is None:
                print("Invalid PR branch ref was generated, hence no PR will be will be opened")
                return
            self.__log.debug("Created PR branch ref %s", pr_branch_ref)

            if not self.repo.create_branch(base_branch, pr_branch_ref):
                print("Unable to create PR branch %s" % self.branch_helper.as_branch_name(pr_branch_ref))
                return
            
            manifest_file_contents = self.__read_file_bytes(os.path.abspath(local_change_relative_path))
            self.__log.debug("Read contents of manifest file %s", local_change_relative_path)
            pdf_report_contents = None
            if pdf_report_path:
                self.__log.debug("Requested addition of PDF report in PR, reading contents...")
                pdf_report_contents = self.__read_file_bytes(os.path.abspath(pdf_report_path))
                self.__log.debug("Read contents of PDF report %s", pdf_report_path)
            
            commit_message = "Update " + manifest_file_name
            
            head = self.repo.get_owner() + ":" + self.branch_helper.as_branch_name(pr_branch_ref)
            pulls = self.repo.get_open_pulls(head=head, base=base_branch)
            self.__log.debug("Retrieved open PRs %s with head=%s and base=%s", pulls, head, base_branch)
            if len(pulls) > 0:
                open_pr = pulls[0] # there could only be 1 pull open from a specific head branch to a specific base branch

                were_changes_committed = self.__do_all_commits(commit_message, self.branch_helper.as_branch_name(pr_branch_ref), local_changes_relative_paths, local_change_relative_path, manifest_file_contents,
                                                               pdf_report_path, pdf_report_contents)
                if were_changes_committed:
                    self.__edit_pr(open_pr, pr_text_content[self.PR_CONTENT_TITLE_KEY], pr_text_content[self.PR_CONTENT_BODY_KEY])
                    print("Existing pull request was found and updated, review it here:\n" + open_pr.get_url())
                else:
                    print("Existing pull request was found, review it here:\n" + open_pr.get_url())
                continue

            pulls = self.repo.get_closed_pulls(head=head, base=base_branch)
            self.__log.debug("Checking closed PRs to see if soon to be opened PR was created before...")
            for closed_pr in pulls:
                if pr_text_content[self.PR_CONTENT_TITLE_KEY] == closed_pr.get_title() and pr_text_content[self.PR_CONTENT_BODY_KEY] == closed_pr.get_body():
                    print("No new pull request will be created as an identical pull request has been closed:\n" + closed_pr.get_url())
                    return
            
            self.__log.debug("No open nor closed PRs detected, pening a new PR...")
            were_changes_committed = self.__do_all_commits(commit_message, self.branch_helper.as_branch_name(pr_branch_ref), local_changes_relative_paths, local_change_relative_path, manifest_file_contents,
                                                           pdf_report_path, pdf_report_contents)
            if were_changes_committed:
                new_pr = self.repo.create_pull_request(pr_text_content[self.PR_CONTENT_TITLE_KEY], pr_text_content[self.PR_CONTENT_BODY_KEY], self.branch_helper.as_branch_name(pr_branch_ref),
                                                       base_branch)
                print("A new pull request has been opened, review it here:\n" + new_pr.get_url())


    def __edit_pr(self, pr: PullRequestInterface, title: str, body: str):
        """Helper method to only edit pr title and body where these actually change"""
        the_title = None
        if title:
            if title !=  pr.get_title():
                the_title = title
        
        the_body = None
        if body:
            if body !=  pr.get_body():
                the_body = body

        pr.edit(title=the_title, body=the_body)

    def __do_all_commits(self, commit_message: str, branch_name: str, local_changes: list, manifest_path: str, manifest_contents: bytes, pdf_report_path: str, pdf_report_contents: bytes) -> bool:
        were_changes_committed = self.repo.commit_change(self.author, commit_message, branch_name, manifest_path, manifest_contents)

        if pdf_report_path:
            commit_verb = "Update" if pdf_report_path in local_changes else "Add"
            commit_msg = commit_verb + " " + os.path.basename(pdf_report_path)
            were_changes_committed |= self.repo.commit_change(self.author, commit_msg, branch_name, pdf_report_path, pdf_report_contents)

        return were_changes_committed

    def __read_file_bytes(self, path: str) -> bytes:
        file = open(path, "rb")
        bytes_contents = file.read()
        file.close()
        return bytes_contents

    def __create_pr_branch_ref(self, name: str, base_branch: str) -> str:
        pr_branch_name = BranchHelper.PR_BRANCH_NAME_PREFIX + name 
        if base_branch != self.repo.get_default_branch():
            pr_branch_name = base_branch + "_" + pr_branch_name
        
        pr_branch_name = self.branch_helper.to_branch_ref(pr_branch_name)
        
        return pr_branch_name