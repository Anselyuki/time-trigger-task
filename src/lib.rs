use glob::glob;
use pyo3::prelude::*;
use serde_json::Value;
use std::fs;

// 1. 扫描目录获取 .json 文件列表
#[pyfunction]
fn list_configs(dir: String) -> PyResult<Vec<String>> {
    let pattern = format!("{}/*.json", dir);
    let mut files = Vec::new();
    if let Ok(paths) = glob(&pattern) {
        for entry in paths {
            if let Ok(path) = entry {
                if let Some(path_str) = path.to_str() {
                    files.push(path_str.to_string());
                }
            }
        }
    }
    // 排序，保证执行顺序稳定
    files.sort();
    Ok(files)
}

// 2. 读取 JSON 并自动转为 Python 字典
#[pyfunction]
fn read_config(path: String, py: Python) -> PyResult<PyObject> {
    // 读取文件字符串
    let content = fs::read_to_string(&path).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("读取失败 {}: {}", path, e))
    })?;
    // 解析为 Rust 的 JSON Value
    let v: Value = serde_json::from_str(&content).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("JSON 格式错误 {}: {}", path, e))
    })?;
    // 转化为 Python 对象 (Dict/List/etc)
    pythonize::pythonize(py, &v)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
}

// 3. 将 Python 字典保存回 JSON 文件
#[pyfunction]
fn save_config(path: String, data: PyObject, py: Python) -> PyResult<()> {
    // 将 Python 对象转回 Rust JSON Value
    let v: Value = pythonize::depythonize(data.as_ref(py)).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "无法转换 Python 对象为 JSON: {}",
            e
        ))
    })?;
    // 格式化输出 (pretty print)
    let content = serde_json::to_string_pretty(&v).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("JSON 序列化失败: {}", e))
    })?;
    fs::write(&path, content).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("写入失败 {}: {}", path, e))
    })?;
    Ok(())
}

// 注册模块 — 使用 `task_io` 扩展名，和包内模块名一致
#[pymodule]
fn task_io(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(list_configs, m)?)?;
    m.add_function(wrap_pyfunction!(read_config, m)?)?;
    m.add_function(wrap_pyfunction!(save_config, m)?)?;
    Ok(())
}
