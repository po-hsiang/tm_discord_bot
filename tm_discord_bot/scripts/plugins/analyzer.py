class Analyzer:
    def __init__(self):
        pass

    def analysis(self):

        self.srt_subtitle, self.subtitle = self.get_subtitle()
        logger.info(f"Subtitle length: {len(self.subtitle)}")

        if not response:
            response = self.summarize_subtitle(self.subtitle, self.subtitle_summarizer, summary_input,
                                               openai_kwargs={"response_format": {"type": "json_object"}})
            response = self.parse_response(self.parse_summary(response))
            logger.info(f"\n[IssueAnalysis] get_reply_msg() response:\n{response}")

        logger.info(f"Total execution time: {time.time() - overall_start}\n")
        return response, self.get_audio(response)
