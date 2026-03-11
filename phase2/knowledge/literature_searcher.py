# -*- coding: utf-8 -*-
"""
Semantic Scholar文献自动检索工具

功能：
1. 批量检索最新文献
2. 提取关键信息
3. 生成文献总结
4. 更新Prompt
"""
import requests
import time
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class LiteratureSearcher:
    """文献检索器"""
    
    def __init__(self, api_key: str):
        """
        初始化
        
        Args:
            api_key: Semantic Scholar API key
        """
        self.api_key = api_key
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.rate_limit = 1.1  # seconds between requests
        
        # 创建目录
        self.lit_dir = Path("phase2/knowledge/literature")
        self.lit_dir.mkdir(parents=True, exist_ok=True)
        
        (self.lit_dir / "core").mkdir(exist_ok=True)
        (self.lit_dir / "supplementary").mkdir(exist_ok=True)
        (self.lit_dir / "metadata").mkdir(exist_ok=True)
        (self.lit_dir / "summaries").mkdir(exist_ok=True)
    
    def search_papers(
        self,
        query: str,
        year_from: int = 2020,
        limit: int = 20,
        fields: str = None
    ) -> Dict[str, Any]:
        """
        搜索论文
        
        Args:
            query: 搜索关键词
            year_from: 起始年份
            limit: 返回数量
            fields: 返回字段
            
        Returns:
            搜索结果
        """
        if fields is None:
            fields = "title,abstract,year,citationCount,authors,venue,url,openAccessPdf,externalIds"
        
        headers = {"x-api-key": self.api_key}
        params = {
            "query": query,
            "year": f"{year_from}-",
            "limit": limit,
            "fields": fields
        }
        
        print(f"[搜索] {query} (>={year_from}年)...")
        
        try:
            response = requests.get(
                f"{self.base_url}/paper/search",
                headers=headers,
                params=params,
                timeout=30
            )
            
            time.sleep(self.rate_limit)  # 遵守rate limit
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] 找到{data.get('total', 0)}篇，返回{len(data.get('data', []))}篇")
                return data
            else:
                print(f"[ERROR] {response.status_code}: {response.text}")
                return {"data": [], "total": 0}
        
        except Exception as e:
            print(f"[ERROR] 请求失败: {e}")
            return {"data": [], "total": 0}
    
    def batch_search(self, topics: Dict[str, Dict]) -> Dict[str, List[Dict]]:
        """
        批量搜索
        
        Args:
            topics: 主题配置
                {
                    "topic_name": {
                        "queries": ["query1", "query2"],
                        "year_from": 2020,
                        "limit": 20
                    }
                }
        
        Returns:
            搜索结果（按主题分组）
        """
        results = {}
        
        for topic_name, config in topics.items():
            print(f"\n{'='*80}")
            print(f"主题: {topic_name}")
            print(f"{'='*80}")
            
            topic_papers = []
            
            for query in config.get("queries", []):
                data = self.search_papers(
                    query=query,
                    year_from=config.get("year_from", 2020),
                    limit=config.get("limit", 20)
                )
                
                topic_papers.extend(data.get("data", []))
            
            # 去重（按paperId）
            seen = set()
            unique_papers = []
            for paper in topic_papers:
                paper_id = paper.get("paperId")
                if paper_id and paper_id not in seen:
                    seen.add(paper_id)
                    unique_papers.append(paper)
            
            # 按引用数排序
            unique_papers.sort(
                key=lambda x: x.get("citationCount", 0),
                reverse=True
            )
            
            results[topic_name] = unique_papers
            print(f"[总计] {topic_name}: {len(unique_papers)}篇（去重后）")
        
        return results
    
    def extract_key_info(self, paper: Dict) -> Dict:
        """
        提取论文关键信息
        
        Args:
            paper: 论文数据
            
        Returns:
            关键信息
        """
        authors = paper.get("authors", [])
        first_author = authors[0].get("name", "Unknown") if authors else "Unknown"
        
        return {
            "paper_id": paper.get("paperId"),
            "title": paper.get("title", ""),
            "authors": [a.get("name") for a in authors],
            "first_author": first_author,
            "year": paper.get("year"),
            "venue": paper.get("venue", "Unknown"),
            "citation_count": paper.get("citationCount", 0),
            "abstract": paper.get("abstract", ""),
            "url": paper.get("url", ""),
            "pdf_url": paper.get("openAccessPdf", {}).get("url") if paper.get("openAccessPdf") else None,
            "doi": paper.get("externalIds", {}).get("DOI")
        }
    
    def save_results(self, results: Dict[str, List[Dict]], output_file: Path):
        """
        保存搜索结果
        
        Args:
            results: 搜索结果
            output_file: 输出文件
        """
        # 提取关键信息
        processed = {}
        for topic, papers in results.items():
            processed[topic] = [self.extract_key_info(p) for p in papers]
        
        # 保存JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)
        
        print(f"\n[保存] 结果已保存: {output_file}")
        
        # 生成统计
        total_papers = sum(len(papers) for papers in processed.values())
        print(f"\n{'='*80}")
        print(f"搜索统计")
        print(f"{'='*80}")
        print(f"主题数: {len(processed)}")
        print(f"论文总数: {total_papers}")
        for topic, papers in processed.items():
            print(f"  - {topic}: {len(papers)}篇")
    
    def generate_summary(self, results: Dict[str, List[Dict]], output_file: Path):
        """
        生成文献总结
        
        Args:
            results: 搜索结果
            output_file: 输出文件
        """
        summary = f"""# 文献检索总结

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**数据源**: Semantic Scholar API  
**检索范围**: 2020-2025年

---

## 📊 总体统计

- **主题数**: {len(results)}
- **论文总数**: {sum(len(papers) for papers in results.values())}

"""
        
        for topic, papers in results.items():
            summary += f"\n## 🔬 主题: {topic}\n\n"
            summary += f"**论文数**: {len(papers)}\n\n"
            
            # Top 5
            summary += "### Top 5论文（按引用数）\n\n"
            for i, paper in enumerate(papers[:5], 1):
                info = self.extract_key_info(paper)
                summary += f"""
#### {i}. {info['title']}

- **作者**: {', '.join(info['authors'][:3])}{'等' if len(info['authors']) > 3 else ''}
- **年份**: {info['year']}
- **期刊**: {info['venue']}
- **引用数**: {info['citation_count']}
- **DOI**: {info['doi'] if info['doi'] else 'N/A'}

**摘要**:
{info['abstract'][:500] if info['abstract'] else 'N/A'}...

**链接**: {info['url']}

---

"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        print(f"[保存] 总结已保存: {output_file}")


def main():
    """主函数"""
    # API key
    API_KEY = "kRxGUYRlqa9t60mIApL2ka77ebkXVrT78on3yMjW"
    
    # 初始化
    searcher = LiteratureSearcher(api_key=API_KEY)
    
    # 定义搜索主题
    topics = {
        "磷酸质子传导机制": {
            "queries": [
                "phosphoric acid proton conduction mechanism",
                "H3PO4 proton transport",
                "packed-acid mechanism phosphoric acid"
            ],
            "year_from": 2020,
            "limit": 15
        },
        "纳米限域质子传导": {
            "queries": [
                "nanoconfinement proton conduction",
                "clay proton conductor",
                "confined phosphoric acid proton"
            ],
            "year_from": 2020,
            "limit": 15
        },
        "低温质子传导": {
            "queries": [
                "low temperature proton conduction mechanism",
                "proton conductor below 200K",
                "frozen state proton transport"
            ],
            "year_from": 2018,
            "limit": 10
        },
        "NMR同位素效应": {
            "queries": [
                "NMR proton dynamics phosphoric acid",
                "deuterium isotope effect proton conduction",
                "solid-state NMR proton conductor"
            ],
            "year_from": 2018,
            "limit": 10
        },
        "Acid-in-Clay材料": {
            "queries": [
                "acid-in-clay proton conductor",
                "clay-based electrolyte proton"
            ],
            "year_from": 2020,
            "limit": 10
        }
    }
    
    print(f"\n{'='*80}")
    print(f"开始文献检索")
    print(f"{'='*80}")
    print(f"API Key: {API_KEY[:20]}...")
    print(f"主题数: {len(topics)}")
    print(f"预计时间: ~{len(topics) * 3 * 1.5 / 60:.1f}分钟")
    
    # 批量搜索
    results = searcher.batch_search(topics)
    
    # 保存结果
    metadata_file = searcher.lit_dir / "metadata" / "paper_database.json"
    searcher.save_results(results, metadata_file)
    
    # 生成总结
    summary_file = searcher.lit_dir / "summaries" / "literature_summary.md"
    searcher.generate_summary(results, summary_file)
    
    print(f"\n{'='*80}")
    print(f"文献检索完成！")
    print(f"{'='*80}")
    print(f"元数据: {metadata_file}")
    print(f"总结: {summary_file}")


if __name__ == "__main__":
    main()

